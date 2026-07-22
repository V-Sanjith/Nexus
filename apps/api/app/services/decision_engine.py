import re
from typing import List, Dict, Any, Optional, Tuple
from uuid import UUID
from pydantic import BaseModel, Field
import math
import structlog
from app.models.product import Product
from app.services.score_calculator import ScoreCalculator

logger = structlog.get_logger()

class DecisionAttribute(BaseModel):
    """Configuration for attributes parsed by the generic Decision Engine."""
    key: str
    name: str
    type: str  # "benefit" (higher is better) | "cost" (lower is better)
    is_hard_filter: bool = False

class ProductScoreResult(BaseModel):
    """Intermediary scoring result for a product."""
    model_config = {"arbitrary_types_allowed": True}
    
    product: Product
    score: float
    confidence_score: float
    scoring_breakdown: Dict[str, float]
    normalized_values: Dict[str, float]
    raw_values: Dict[str, Any]
    configurations: List[Dict[str, Any]] = Field(default_factory=list)

class DecisionEngine:
    """Deterministic 8-stage Multi-Criteria Decision Analysis (MCDA) Scoring Engine."""

    @staticmethod
    def _safe_float(val: Any, default: float = 0.0) -> float:
        if val is None:
            return default
        if isinstance(val, (int, float)):
            return float(val)
        if isinstance(val, str):
            val = val.strip()
            try:
                return float(val)
            except ValueError:
                pass
            match = re.search(r'[-+]?\d*\.\d+|\d+', val)
            if match:
                try:
                    return float(match.group(0))
                except ValueError:
                    pass
        return default

    def __init__(self, category_config: Any):
        """
        Constructor accepting a category/subtype configuration bundle.
        """
        self.config = category_config
        
        # Support both CategoryConfig Pydantic model and raw dictionary
        if hasattr(category_config, 'category'):
            self.category = category_config.category.lower()
            attrs = category_config.attributes
        else:
            self.category = category_config.get('category', '').lower()
            attrs = category_config.get('attributes', [])
            
        self.attributes = []
        for attr in attrs:
            if hasattr(attr, 'key'):
                self.attributes.append(
                    DecisionAttribute(
                        key=attr.key,
                        name=attr.name,
                        type=attr.type,
                        is_hard_filter=attr.is_hard_filter
                    )
                )
            else:
                self.attributes.append(
                    DecisionAttribute(
                        key=attr.get('key'),
                        name=attr.get('name'),
                        type=attr.get('type'),
                        is_hard_filter=attr.get('is_hard_filter', False)
                    )
                )

    def parse_query_intent(self, query: str, default_category: str, default_subtype: str) -> Tuple[str, str, Optional[float]]:
        """Stage 2: Deterministic query intent parser."""
        q = query.lower().strip()
        
        # 1. Detect Category
        category = default_category
            
        # 2. Detect Subtype
        subtype = default_subtype
            
        # 3. Detect Budget (e.g. ₹100000, 100k, rs 60000, rs. 60k, 40k)
        budget = None
        # Match 'k' suffix e.g. 40k, 100k, but avoid matching 4k as 4000 for display
        match_k = re.search(r'\b(\d{2,})\s*k\b', q)
        if match_k:
            budget = float(match_k.group(1)) * 1000.0
        else:
            # Match digits after currency indicators
            match_num = re.search(r'(?:rs\.?|inr|rupees|₹|under|below|budget)\s*(\d[\d,.]*)', q)
            if match_num:
                num_str = match_num.group(1).replace(',', '')
                try:
                    budget = float(num_str)
                except ValueError:
                    pass
            
            if not budget:
                # Fallback: find any 4-6 digit number representing a price point
                nums = re.findall(r'\b\d{4,6}\b', q)
                if nums:
                    val = float(nums[0])
                    # Ignore 4000 if it looks like a 4K monitor query
                    if 5000 <= val <= 500000:
                        budget = val
                        
        return category, subtype, budget

    def run(
        self,
        products: List[Product],
        answers: List[Dict[str, Any]],
        persona_hint: Optional[str] = None,
        custom_persona_weights: Optional[Dict[str, float]] = None,
        intent_confidence: Optional[float] = None,
        currency_code: str = "usd",
        currency_symbol: str = "$",
        query: Optional[str] = None
    ) -> Tuple[List[ProductScoreResult], Dict[str, Any], str]:
        """
        Executes the strict 8-stage deterministic decision pipeline.
        """
        import time
        from app.services.currency_service import CurrencyService

        # ---------------------------------------------------------
        # STAGE 1: User Query
        # ---------------------------------------------------------
        raw_query = query or ""
        logger.info("Stage 1: User Query received", query=raw_query)

        # ---------------------------------------------------------
        # STAGE 2: Intent Detection
        # ---------------------------------------------------------
        config_subtype = getattr(self.config, 'subtype', 'general') or 'general'
        if isinstance(self.config, dict):
            config_subtype = self.config.get('subtype', 'general') or 'general'

        detected_category, detected_subtype, detected_budget = self.parse_query_intent(
            raw_query, 
            default_category=self.category, 
            default_subtype=config_subtype
        )
        
        # Fallback to answers if budget is not in query title
        user_pref: Dict[str, Any] = {}
        priorities: Dict[str, float] = {}

        # Default weights for all soft attributes
        for attr in self.attributes:
            if not attr.is_hard_filter:
                priorities[attr.key] = 3.0

        # Extract values from answers
        for ans in answers:
            if hasattr(ans, 'question') and ans.question:
                q = ans.question
                val = ans.selected_value.get("value") if isinstance(ans.selected_value, dict) else ans.selected_value
            elif isinstance(ans, dict):
                q = ans.get("question")
                val = ans.get("selected_value", {}).get("value") if isinstance(ans.get("selected_value"), dict) else ans.get("selected_value")
            else:
                continue
                
            val_f = None
            if val is not None:
                try:
                    if isinstance(val, str) and val in ["Yes", "No"]:
                        val_f = val
                    else:
                        val_f = float(val)
                except ValueError:
                    val_f = val

            if val_f is None:
                continue

            maps_to = None
            if q:
                if hasattr(q, 'weight_impact') and q.weight_impact:
                    maps_to = q.weight_impact.get("maps_to")
                elif isinstance(q, dict) and q.get("weight_impact"):
                    maps_to = q.get("weight_impact", {}).get("maps_to")
                
                if not maps_to:
                    q_text = (q.question_text if hasattr(q, 'question_text') else q.get('question_text', '')).lower()
                    if "budget" in q_text or "price" in q_text:
                        maps_to = "price"
                    elif "linux" in q_text:
                        maps_to = "need_linux"
            
            if not maps_to and isinstance(ans, dict) and "question_text" in ans:
                q_text = ans["question_text"].lower()
                if "budget" in q_text or "price" in q_text:
                    maps_to = "price"
                elif "linux" in q_text:
                    maps_to = "need_linux"
            
            if not maps_to:
                continue

            user_pref[maps_to] = val_f
            if isinstance(val_f, (int, float)) and maps_to != "price":
                # Only add to priorities if it is a soft attribute
                is_soft = any(attr.key == maps_to and not attr.is_hard_filter for attr in self.attributes)
                if is_soft:
                    input_type = getattr(q, "input_type", None) or (q.get("input_type") if isinstance(q, dict) else None)
                    if input_type == "single_choice":
                        priorities[maps_to] = 3.0
                    else:
                        priorities[maps_to] = float(val_f)

        # Determine budget in local currency
        # Explicit answers (e.g. from the UI slider) take precedence over the flaky regex parser!
        local_budget = user_pref.get("price")
        if local_budget is None:
            local_budget = detected_budget

        # In this Engine, all catalog products are stored in INR natively (price_inr)
        # So budget_inr must just be the local_budget if currency is INR
        is_inr = "₹" in raw_query or "rs" in raw_query.lower() or "inr" in raw_query.lower() or currency_code == "inr"
        
        budget_inr = None
        if local_budget is not None:
            if is_inr:
                budget_inr = float(local_budget)
            else:
                # If the query was in USD, convert USD to INR so it matches our catalog
                budget_inr = CurrencyService.convert_from_usd(local_budget, "inr")

        logger.info("Stage 2: Intent parsed", category=detected_category, subtype=detected_subtype, local_budget=local_budget, budget_inr=budget_inr)

        # ---------------------------------------------------------
        # STAGE 3: Category Detection
        # ---------------------------------------------------------
        stage3_output = []
        for p in products:
            if p.category == detected_category:
                stage3_output.append(p)
        
        logger.info("Stage 3: Category Detection completed", category=detected_category, count=len(stage3_output))

        # ---------------------------------------------------------
        # STAGE 4: Catalog Loading
        # ---------------------------------------------------------
        # All category products loaded
        stage4_output = list(stage3_output)
        logger.info("Stage 4: Catalog Loading completed", count=len(stage4_output))

        # ---------------------------------------------------------
        # STAGE 5: Hard Filters (Strict, Binary Constraints)
        # ---------------------------------------------------------
        # Apply filters sequentially, logging the count after each stage
        stage5_trace = []
        current_pool = list(stage4_output)
        rejections = {}
        rejections_by_reason = {}

        def get_product_subtype(p: Product) -> str:
            if p.category == "laptop":
                sub = p.specs.get("laptop_type", "general")
                if sub == "developer":
                    return "developer"
                return sub
            elif p.category == "smartphone":
                return p.specs.get("phone_type", "general")
            elif p.category == "monitor":
                sub = p.specs.get("monitor_type", "general")
                if sub == "designer":
                    return "design"
                if sub == "professional" or sub == "productivity":
                    return "general" # fallback since we only have design/gaming monitors
                return sub
            return "general"

        # A. Subtype Filter
        t_subtype_start = time.perf_counter()
        subtype_filtered = []
        for p in current_pool:
            p_sub = get_product_subtype(p)
            mapped_detected = detected_subtype
            if detected_category == "laptop" and detected_subtype == "programming":
                mapped_detected = "developer"
            elif detected_category == "monitor":
                if detected_subtype == "designer":
                    mapped_detected = "design"
                elif detected_subtype == "productivity":
                    mapped_detected = "general"
                    detected_subtype = "general" # Ensure it matches all monitor types as a fallback

            # Flagship smartphones and premium laptops match any subtype request
            is_match = (
                detected_subtype == "general" or 
                p_sub == mapped_detected or 
                (detected_category == "smartphone" and p_sub == "flagship") or 
                (detected_category == "laptop" and p_sub == "premium")
            )
            if detected_category == "laptop" and mapped_detected == "developer":
                is_match = is_match or p_sub in ["business", "general"]

            if is_match:
                subtype_filtered.append(p)
            else:
                rejections[p.sku] = f"Subtype '{p_sub}' does not match required '{detected_subtype}'"
                rejections_by_reason["subtype"] = rejections_by_reason.get("subtype", 0) + 1
        
        current_pool = subtype_filtered
        stage5_trace.append(("Subtype", len(current_pool), (time.perf_counter() - t_subtype_start) * 1000.0))

        # B. GPU Filter (For Gaming Laptops only)
        t_gpu_start = time.perf_counter()
        gpu_filtered = []
        for p in current_pool:
            if p.category == "laptop" and detected_subtype == "gaming":
                if p.specs.get("gpu_type") == "dedicated":
                    gpu_filtered.append(p)
                else:
                    rejections[p.sku] = "Requires dedicated GPU for gaming"
                    rejections_by_reason["gpu"] = rejections_by_reason.get("gpu", 0) + 1
            else:
                gpu_filtered.append(p)
                
        current_pool = gpu_filtered
        stage5_trace.append(("GPU", len(current_pool), (time.perf_counter() - t_gpu_start) * 1000.0))

        # C. Budget Filter (Absolute: price <= budget)
        t_budget_start = time.perf_counter()
        budget_filtered = []
        
        if budget_inr is not None:
            for p in current_pool:
                p_price = float(p.price_inr)
                if p_price <= budget_inr:
                    budget_filtered.append(p)
                else:
                    rejections[p.sku] = f"Price {currency_symbol}{p_price:,.0f} exceeded maximum budget of {currency_symbol}{budget_inr:,.0f}"
                    rejections_by_reason["price"] = rejections_by_reason.get("price", 0) + 1
        else:
            budget_filtered = list(current_pool)
            
        current_pool = budget_filtered
        stage5_trace.append(("Budget", len(current_pool), (time.perf_counter() - t_budget_start) * 1000.0))

        # D. Linux Support Filter
        t_linux_start = time.perf_counter()
        linux_filtered = []
        need_linux = user_pref.get("need_linux") == "Yes"
        for p in current_pool:
            if need_linux:
                if p.specs.get("linux_supported") is True:
                    linux_filtered.append(p)
                else:
                    rejections[p.sku] = "Does not support Linux natively"
                    rejections_by_reason["linux"] = rejections_by_reason.get("linux", 0) + 1
            else:
                linux_filtered.append(p)
        
        current_pool = linux_filtered
        stage5_trace.append(("LinuxSupport", len(current_pool), (time.perf_counter() - t_linux_start) * 1000.0))

        # E. Stock Filter
        t_stock_start = time.perf_counter()
        stock_filtered = []
        for p in current_pool:
            if p.specs.get("stock", True) is not False:
                stock_filtered.append(p)
            else:
                rejections[p.sku] = "Out of stock"
                rejections_by_reason["stock"] = rejections_by_reason.get("stock", 0) + 1
                
        current_pool = stock_filtered
        stage5_trace.append(("Stock", len(current_pool), (time.perf_counter() - t_stock_start) * 1000.0))

        # Log pipeline trace counts
        pipeline_trace_log = {
            "Loaded": len(stage4_output),
            "Subtype": stage5_trace[0][1],
            "GPU": stage5_trace[1][1],
            "Budget": stage5_trace[2][1],
            "LinuxSupport": stage5_trace[3][1],
            "Stock": stage5_trace[4][1],
        }
        
        # Log to stdout as requested:
        print(f"\n[Pipeline Trace for '{raw_query}']")
        print(f"  Loaded        -> {pipeline_trace_log['Loaded']}")
        print(f"  Subtype       -> {pipeline_trace_log['Subtype']}")
        print(f"  GPU           -> {pipeline_trace_log['GPU']}")
        print(f"  Budget        -> {pipeline_trace_log['Budget']}")
        print(f"  LinuxSupport  -> {pipeline_trace_log['LinuxSupport']}")
        print(f"  Stock         -> {pipeline_trace_log['Stock']}")

        # Track filtered out SKUs
        filtered_out_skus = set(p.sku for p in stage4_output) - set(p.sku for p in current_pool)

        trace = {
            "applied_constraints": {"price_max": budget_inr} if budget_inr is not None else {},
            "catalog_filtered_out": list(filtered_out_skus),
            "rejections": rejections,
            "rejections_by_reason": rejections_by_reason,
            "normalized_weights": {},
            "scoring_breakdown": {},
            "ranking": [],
            "status": "success",
            "closest_matches": [],
            "pipeline_trace": [
                {"stage": 1, "name": "User Query", "count": 1, "time_ms": 0.0},
                {"stage": 2, "name": "Intent Detection", "count": 1, "time_ms": 0.0},
                {"stage": 3, "name": "Category Detection", "count": len(stage3_output), "time_ms": 0.0},
                {"stage": 4, "name": "Catalog Loading", "count": len(stage4_output), "time_ms": 0.0},
                {"stage": 5, "name": "Hard Filters", "details": pipeline_trace_log, "time_ms": sum(t[2] for t in stage5_trace)}
            ]
        }

        # If 0 products remain after hard filtering, stop immediately and return closest matches diagnostics
        if len(current_pool) == 0:
            print("  Winner        -> No Match")
            trace["status"] = "no_match_found"
            
            # Find closest matches from the category pool (excluding budget)
            closest_candidates = []
            for p in stage3_output:
                p_price = float(p.price_inr)
                checks = []
                total_distance = 0.0
                
                # Check Subtype Mismatch Penalty
                p_sub = get_product_subtype(p)
                mapped_detected = detected_subtype
                if detected_category == "laptop" and detected_subtype == "programming":
                    mapped_detected = "developer"
                elif detected_category == "monitor":
                    if detected_subtype == "designer":
                        mapped_detected = "design"
                    elif detected_subtype == "productivity":
                        mapped_detected = "general"
                        
                is_match = (
                    detected_subtype == "general" or 
                    p_sub == mapped_detected or 
                    (detected_category == "smartphone" and p_sub == "flagship") or 
                    (detected_category == "laptop" and p_sub == "premium")
                )
                if detected_category == "laptop" and mapped_detected == "developer":
                    is_match = is_match or p_sub in ["business", "general"]
                    
                if not is_match:
                    total_distance += 10.0
                
                # Check budget
                if budget_inr is not None:
                    if p_price > budget_inr:
                        diff_local = p_price - budget_inr
                        deviation_percent = (p_price - budget_inr) / budget_inr
                        total_distance += deviation_percent * 2.0
                        checks.append({
                            "key": "price",
                            "label": "Budget",
                            "status": "fail",
                            "value": f"{currency_symbol}{p_price:,.0f}",
                            "deviation": f"+{currency_symbol}{diff_local:,.0f}"
                        })
                    else:
                        checks.append({
                            "key": "price",
                            "label": "Budget",
                            "status": "pass",
                            "value": f"{currency_symbol}{p_price:,.0f}",
                            "deviation": ""
                        })

                closest_candidates.append({
                    "product": p,
                    "distance": total_distance,
                    "checks": checks,
                    "reason_failed": f"exceeded maximum budget of {currency_symbol}{CurrencyService.convert_from_usd(budget_inr, 'inr' if is_inr else currency_code):,.0f}" if budget_inr and p_price > budget_inr else "failed compatibility checks"
                })
                
            closest_candidates.sort(key=lambda x: x["distance"])
            
            trace["closest_matches"] = []
            for idx, cand in enumerate(closest_candidates[:3]):
                p = cand["product"]
                trace["closest_matches"].append({
                    "rank": idx + 1,
                    "sku": p.sku,
                    "name": p.name,
                    "price": float(p.price_inr),
                    "distance": float(cand["distance"]),
                    "checks": cand["checks"],
                    "reason_failed": cand["reason_failed"]
                })
            allowed_candidates = [c for c in closest_candidates if budget_inr is None or float(c["product"].price_inr) <= budget_inr]
            if allowed_candidates and allowed_candidates[0]["distance"] < 2.5:
                fallback_winner = allowed_candidates[0]["product"]
                print(f"  Fallback      -> {fallback_winner.name} (distance: {allowed_candidates[0]['distance']:.2f})")
                trace["status"] = "success_with_fallback"
                trace["scoring_breakdown"] = {fallback_winner.sku: {"fallback_override": 1.0}}
                trace["normalized_weights"] = {"fallback": 1.0}
                trace["ranking"] = [fallback_winner.sku]
                
                # Wrap in ProductScoreResult
                fallback_res = ProductScoreResult(
                    product=fallback_winner,
                    score=1.0,
                    confidence_score=40.0,
                    scoring_breakdown={"fallback_override": 1.0},
                    normalized_values={},
                    raw_values={},
                    configurations=[]
                )
                
                return [fallback_res], trace, "success"
                
            return [], trace, "no_match_found"

        # ---------------------------------------------------------
        # STAGE 5.5: Pareto Dominance Filtering
        # ---------------------------------------------------------
        t_pareto_start = time.perf_counter()
        current_pool, pareto_analysis = self._apply_pareto_filtering(current_pool, priorities)
        trace["pareto_analysis"] = pareto_analysis
        trace["pipeline_trace"].append({
            "stage": 5.5,
            "name": "Pareto Dominance Filtering",
            "count": len(current_pool),
            "time_ms": (time.perf_counter() - t_pareto_start) * 1000.0
        })
        print(f"  Pareto        -> {len(current_pool)} (dominated: {len(pareto_analysis['dominated_products'])})")

        # ---------------------------------------------------------
        # STAGE 6: Soft Scoring (MCDA)
        # ---------------------------------------------------------
        t_mcda_start = time.perf_counter()
        
        # Inferred persona and load multipliers
        mock_hard_filters = {"price": {"max": budget_inr}} if budget_inr is not None else {}
        inferred_persona = self._infer_persona(mock_hard_filters, priorities)
        applied_persona = (persona_hint or inferred_persona).lower().strip()
        
        config_personas = self.config.personas if hasattr(self.config, 'personas') else self.config.get('personas', {})
        if custom_persona_weights:
            multipliers = custom_persona_weights
        elif applied_persona in config_personas:
            multipliers = config_personas[applied_persona]
        else:
            applied_persona = "general"
            multipliers = config_personas.get("general", {})
            
        trace["inferred_persona"] = inferred_persona
        trace["applied_persona"] = applied_persona
        trace["persona_weights_applied"] = multipliers

        # Calculate adjusted priority weights
        adjusted_priorities = {}
        for key, p_val in priorities.items():
            mult = multipliers.get(key, 1.0)
            adjusted_priorities[key] = p_val * mult
            
        sum_prio = sum(adjusted_priorities.values())
        normalized_weights: Dict[str, float] = {}
        for key, val in adjusted_priorities.items():
            normalized_weights[key] = val / sum_prio if sum_prio > 0 else 1.0 / len(priorities)
        trace["normalized_weights"] = normalized_weights

        # Performance Optimization: Calculate and cache scores once per product in pool
        product_calculated_scores = {}
        for p in current_pool:
            product_calculated_scores[p.sku] = ScoreCalculator.calculate_all(self.category, p.specs, float(p.price_inr))

        # Establish boundaries for normalization (using only surviving products)
        boundaries: Dict[str, Dict[str, float]] = {}
        soft_attributes = [a for a in self.attributes if not a.is_hard_filter]
        
        for attr in soft_attributes:
            vals = []
            for p in current_pool:
                calculated_scores = product_calculated_scores[p.sku]
                
                # Apply key aliasing
                raw_val = p.specs.get(attr.key)
                if raw_val is None:
                    if attr.key == "battery_hours":
                        raw_val = p.specs.get("estimated_office_hours")
                    elif attr.key == "cpu_score":
                        raw_val = p.specs.get("cpu_multi_core") or p.specs.get("processor_score")
                    elif attr.key == "gpu_score":
                        raw_val = p.specs.get("gpu_score_3dmark")
                
                val = raw_val if raw_val is not None else calculated_scores.get(attr.key)
                if val is not None:
                    vals.append(DecisionEngine._safe_float(val))
            if vals:
                boundaries[attr.key] = {"min": min(vals), "max": max(vals)}
            else:
                boundaries[attr.key] = {"min": 0.0, "max": 1.0}

        # First Pass: Calculate raw performance sums, raw value scores, and budget utilization
        raw_value_scores: Dict[str, float] = {}
        budget_utilization_scores: Dict[str, float] = {}
        
        for p in current_pool:
            calculated_scores = product_calculated_scores[p.sku]
            raw_values = {"price": float(p.price_inr)}
            for k, v in p.specs.items():
                raw_values[k] = v
            for k, v in calculated_scores.items():
                raw_values[k] = v
                
            if "estimated_office_hours" in raw_values:
                raw_values["battery_hours"] = raw_values["estimated_office_hours"]
            if "cpu_multi_core" in raw_values:
                raw_values["cpu_score"] = raw_values["cpu_multi_core"]
            if "gpu_score_3dmark" in raw_values:
                raw_values["gpu_score"] = raw_values["gpu_score_3dmark"]
                
            perf_sum = 0.0
            for attr in soft_attributes:
                val = DecisionEngine._safe_float(raw_values.get(attr.key), 0.0)
                limits = boundaries[attr.key]
                v_min = limits["min"]
                v_max = limits["max"]
                
                if v_max > v_min:
                    if attr.type == "benefit":
                        norm_val = (val - v_min) / (v_max - v_min)
                    else:
                        norm_val = (v_max - val) / (v_max - v_min)
                else:
                    norm_val = 1.0
                    
                if attr.type == "benefit" and attr.key != "price":
                    perf_sum += norm_val
                    
            # Value Score = Performance Score / Price (scaled in thousands)
            price_k = float(p.price_inr) / 1000.0
            raw_value_scores[p.sku] = perf_sum / max(1.0, price_k)
            
            if budget_inr and budget_inr > 0:
                budget_utilization_scores[p.sku] = float(p.price_inr) / budget_inr
            else:
                budget_utilization_scores[p.sku] = 0.0
                
        val_min = min(raw_value_scores.values()) if raw_value_scores else 0.0
        val_max = max(raw_value_scores.values()) if raw_value_scores else 1.0

        # Second Pass: Calculate final utility scores combining MCDA, Value Score, and Budget Utilization
        mcda_results = []
        for p in current_pool:
            scoring_breakdown: Dict[str, float] = {}
            normalized_values: Dict[str, float] = {}
            
            calculated_scores = product_calculated_scores[p.sku]
            raw_values = {"price": float(p.price_inr)}
            for k, v in p.specs.items():
                raw_values[k] = v
            for k, v in calculated_scores.items():
                raw_values[k] = v
                
            if "estimated_office_hours" in raw_values:
                raw_values["battery_hours"] = raw_values["estimated_office_hours"]
            if "cpu_multi_core" in raw_values:
                raw_values["cpu_score"] = raw_values["cpu_multi_core"]
            if "gpu_score_3dmark" in raw_values:
                raw_values["gpu_score"] = raw_values["gpu_score_3dmark"]
                
            base_utility = 0.0
            for attr in soft_attributes:
                val = DecisionEngine._safe_float(raw_values.get(attr.key), 0.0)
                limits = boundaries[attr.key]
                v_min = limits["min"]
                v_max = limits["max"]
                
                if v_max == v_min:
                    norm_val = 1.0
                else:
                    if attr.type == "benefit":
                        norm_val = (val - v_min) / (v_max - v_min)
                    else:
                        norm_val = (v_max - val) / (v_max - v_min)
                        
                normalized_values[attr.key] = norm_val
                weighted_val = norm_val * normalized_weights.get(attr.key, 0.0)
                scoring_breakdown[attr.key] = weighted_val
                base_utility += weighted_val
                
        # Normalize and apply Value Score
            raw_val_sc = raw_value_scores[p.sku]
            norm_val_sc = (raw_val_sc - val_min) / (val_max - val_min) if val_max > val_min else 1.0
            
            # Budget Utilization bonus (up to 0.08 bonus if 80-100% utilized, no penalty if underutilized but specs rule)
            util = budget_utilization_scores[p.sku]
            util_bonus = 0.0
            if 0.8 <= util <= 1.0:
                util_bonus = 0.08
            elif 0.6 <= util < 0.8:
                util_bonus = 0.04
                
            # Combine scores: 95% soft MCDA attributes, 5% Value Score, plus budget utilization bonus
            combined_score = base_utility * 0.95 + norm_val_sc * 0.05 + util_bonus
            combined_score = round(min(1.0, max(0.0, combined_score)), 4)
            
            # Inject metrics into raw_values for tracking and explainability
            raw_values["value_score"] = norm_val_sc
            raw_values["budget_utilization"] = util
            
            normalized_values["value_score"] = norm_val_sc
            normalized_values["budget_utilization"] = util
            scoring_breakdown["value_score"] = norm_val_sc * 0.05
            scoring_breakdown["budget_utilization"] = util_bonus
            
            mcda_results.append(ProductScoreResult(
                product=p,
                score=combined_score,
                confidence_score=90.0,
                scoring_breakdown=scoring_breakdown,
                normalized_values=normalized_values,
                raw_values=raw_values
            ))
            
        mcda_time = (time.perf_counter() - t_mcda_start) * 1000.0
        trace["pipeline_trace"].append({"stage": 6, "name": "Soft Scoring (MCDA)", "count": len(mcda_results), "time_ms": mcda_time})
            
        # ---------------------------------------------------------
        # STAGE 7: Ranking
        # ---------------------------------------------------------
        t_ranking_start = time.perf_counter()
        
        # Sort initial MCDA results to ensure highest score comes first
        mcda_results.sort(key=lambda x: (-x.score, -x.raw_values.get("budget_utilization", 0.0)))

        # STAGE 7A: Alternative Deduplication (Group by Canonical Family)
        family_best: Dict[str, ProductScoreResult] = {}
        family_configurations: Dict[str, List[Dict[str, Any]]] = {}

        for r in mcda_results:
            # Extract Canonical Family Name (e.g. 'ASUS ROG Zephyrus G14 (16GB RAM, 512GB SSD)' -> 'ASUS ROG Zephyrus G14')
            name_parts = r.product.name.split(" (")
            family = name_parts[0].strip()
            
            # Store configuration details
            if family not in family_configurations:
                family_configurations[family] = []
            
            config_name = name_parts[1].replace(")", "") if len(name_parts) > 1 else "Standard"
            family_configurations[family].append({
                "sku": r.product.sku,
                "name": config_name,
                "price_inr": float(r.product.price_inr),
                "specs": r.product.specs
            })

            # Keep only the highest-scoring product per family
            if family not in family_best:
                family_best[family] = r
                
        # Rebuild mcda_results with deduped best-in-family products
        mcda_results = list(family_best.values())
        
        # Attach configurations to the retained ProductScoreResults
        for r in mcda_results:
            family = r.product.name.split(" (")[0].strip()
            r.configurations = family_configurations[family]

        # Calculate dynamic confidence scores
        if len(mcda_results) >= 2:
            gap = mcda_results[0].score - mcda_results[1].score
            gap_factor = 0.8 + min(0.2, gap * 2.0)
        else:
            gap_factor = 1.0
            
        for r in mcda_results:
            det_factor = float(intent_confidence or 95.0) / 100.0
            spec_keys_checked = len([k for k in r.product.specs.keys() if r.product.specs[k] is not None])
            spec_factor = spec_keys_checked / max(1, len(self.attributes))
            cov_factor = len(current_pool) / len(products) if products else 1.0
            
            r.confidence_score = 100.0 * (det_factor * spec_factor * cov_factor * gap_factor)
            r.confidence_score = max(30.0, min(99.0, r.confidence_score))

        # Apply diversity penalty ONLY to top 100 to avoid O(N^2) bottleneck
        top_candidates = mcda_results[:100]
        diverse_results: List[ProductScoreResult] = []
        for candidate in top_candidates:
            penalty = 0.0
            for selected in diverse_results:
                sim = self._calculate_similarity(candidate, selected)
                if sim > 0.70:
                    penalty += 0.20 * (sim - 0.70)
            candidate.score -= penalty
            diverse_results.append(candidate)
            
        # Final Sort after diversity penalty
        diverse_results.sort(key=lambda x: (-x.score, -x.raw_values.get("budget_utilization", 0.0), -x.confidence_score))

        # Re-attach the bottom candidates (unpenalized) so we don't lose them, but we only trace the top 100
        diverse_results.extend(mcda_results[100:])

        # Populate trace ranking logs (limit to top 100 to avoid massive JSON payloads)
        for idx, res in enumerate(diverse_results[:100]):
            trace["ranking"].append({
                "rank": idx + 1,
                "sku": res.product.sku,
                "name": res.product.name,
                "score": float(res.score),
                "confidence_score": float(res.confidence_score),
                "price": float(res.product.price_inr)
            })
            trace["scoring_breakdown"][res.product.sku] = {
                "final_score": float(res.score),
                "normalized_utilities": {k: float(v) for k, v in res.normalized_values.items()},
                "weighted_utilities": {k: float(v) for k, v in res.scoring_breakdown.items()}
            }
            # Optional: trace configurations count
            trace["ranking"][-1]["configurations_count"] = len(res.configurations)

        winner = diverse_results[0].product
        ranking_time = (time.perf_counter() - t_ranking_start) * 1000.0
        trace["pipeline_trace"].append({"stage": 7, "name": "Ranking", "count": len(diverse_results), "time_ms": ranking_time})
        
        print(f"  MCDA          -> {len(diverse_results)}")
        print(f"  Winner        -> {winner.name}\n")

        # ---------------------------------------------------------
        # STAGE 8: Explanation
        # ---------------------------------------------------------
        # Handled downstream in RecommendationService via ExplanationBuilder
        return diverse_results, trace, "success"

    def _infer_persona(self, hard_filters: Dict[str, Any], priorities: Dict[str, float]) -> str:
        """Heuristically determines user persona based on priority sliders and budget constraints."""
        category_name = self.category
        budget = hard_filters.get("price", {}).get("max")
        
        if category_name == "laptop":
            scores = {"gamer": 0, "developer": 0, "video editor": 0, "traveller": 0, "student": 0, "business user": 0}
            
            # Budget-based adjustments
            if budget:
                if budget >= 90000.0:
                    scores["developer"] += 2
                    scores["gamer"] += 2
                    scores["video editor"] += 2
                elif budget <= 60000.0:
                    scores["student"] += 2
            
            gpu = priorities.get("gpu_score", 3.0)
            cpu = priorities.get("cpu_score", 3.0)
            weight = priorities.get("weight_kg", 3.0)
            battery = priorities.get("battery_hours", 3.0)

            if gpu >= 4.0:
                scores["gamer"] += 3
                scores["video editor"] += 2
            if cpu >= 4.0:
                scores["developer"] += 2
                scores["video editor"] += 2
            if weight >= 4.0:
                scores["traveller"] += 3
                scores["business user"] += 1
            if battery >= 4.0:
                scores["traveller"] += 1
                scores["business user"] += 2
                if not (budget and budget >= 90000.0):
                    scores["student"] += 1

            best_score = 0
            best_persona = "general"
            for p, score in scores.items():
                if score > best_score:
                    best_score = score
                    best_persona = p
            return best_persona
        elif category_name == "smartphone":
            scores = {"photographer": 0, "gamer": 0, "professional": 0, "student": 0}
            
            # Budget-based adjustments
            if budget:
                if budget >= 45000.0:
                    scores["professional"] += 2
                    scores["photographer"] += 2
                    scores["gamer"] += 2
                elif budget <= 25000.0:
                    scores["student"] += 2
                    
            camera = priorities.get("camera_mp", 3.0)
            gaming = priorities.get("processor_score", 3.0)
            battery = priorities.get("battery_mah", 3.0)
            
            if camera >= 4.0:
                scores["photographer"] += 3
            if gaming >= 4.0:
                scores["gamer"] += 3
            if battery >= 4.0:
                if not (budget and budget >= 45000.0):
                    scores["student"] += 2
                scores["professional"] += 1
                
            best_score = 0
            best_persona = "general"
            for p, score in scores.items():
                if score > best_score:
                    best_score = score
                    best_persona = p
            return best_persona
        elif category_name == "monitor":
            scores = {"gamer": 0, "designer": 0, "developer": 0}
            refresh = priorities.get("refresh_rate_hz", 3.0)
            accuracy = priorities.get("color_accuracy_score", 3.0)
            size = priorities.get("screen_size_inches", 3.0)
            
            if refresh >= 4.0:
                scores["gamer"] += 3
            if accuracy >= 4.0:
                scores["designer"] += 3
            if size >= 4.0:
                scores["developer"] += 2
                
            best_score = 0
            best_persona = "general"
            for p, score in scores.items():
                if score > best_score:
                    best_score = score
                    best_persona = p
            return best_persona
            
        return "general"

    def _calculate_similarity(self, a: ProductScoreResult, b: ProductScoreResult) -> float:
        """Calculates pairwise specs + intended use case similarity (0.0 to 1.0)."""
        sim_config = self.config.similarity_keys if hasattr(self.config, 'similarity_keys') else {}
        if not sim_config and isinstance(self.config, dict):
            sim_config = self.config.get('similarity_keys', {})

        use_case_key = sim_config.use_case_key if hasattr(sim_config, 'use_case_key') else sim_config.get('use_case_key')
        if use_case_key:
            a_type = str(a.raw_values.get(use_case_key, "")).lower()
            b_type = str(b.raw_values.get(use_case_key, "")).lower()
            use_case_sim = 1.0 if a_type == b_type and a_type else 0.0
        else:
            use_case_sim = 0.0

        spec_keys = sim_config.spec_keys if hasattr(sim_config, 'spec_keys') else sim_config.get('spec_keys', [])
        if not spec_keys:
            spec_sim = 1.0
        else:
            dist = 0.0
            for k in spec_keys:
                diff = abs(a.normalized_values.get(k, 0.5) - b.normalized_values.get(k, 0.5))
                dist += diff
            spec_sim = 1.0 - (dist / len(spec_keys))
            
        brand_a = str(a.product.specs.get("brand", "")).lower().strip()
        brand_b = str(b.product.specs.get("brand", "")).lower().strip()
        brand_sim = 1.0 if brand_a == brand_b and brand_a else 0.0

        return 0.2 * spec_sim + 0.3 * use_case_sim + 0.5 * brand_sim

    @staticmethod
    def calculate_tradeoffs(
        winner: ProductScoreResult,
        alternatives: List[ProductScoreResult],
        tradeoff_config: Optional[List[Any]] = None,
        currency_code: str = "usd",
        currency_symbol: str = "$"
    ) -> List[Dict[str, Any]]:
        """
        Calculates specifications and pricing tradeoff comparisons between the winner and alternatives.
        """
        if tradeoff_config is None:
            tradeoff_config = [
                {"key": "ram_gb", "name": "RAM", "type": "benefit", "unit": "GB", "format_int": True},
                {"key": "storage_gb", "name": "Storage", "type": "benefit", "unit": "GB", "format_int": True},
                {"key": "weight_kg", "name": "Weight", "type": "cost", "unit": "kg", "precision": 2},
                {"key": "estimated_office_hours", "name": "Battery Life", "type": "benefit", "unit": "hours", "precision": 1},
                {"key": "cpu_multi_core", "name": "CPU Power", "type": "benefit", "unit": "pts", "format_int": True},
                {"key": "gpu_score_3dmark", "name": "Graphics power", "type": "benefit", "unit": "pts", "format_int": True},
            ]

        tradeoffs = []
        from app.services.currency_service import CurrencyService

        for alt in alternatives:
            alt_product = alt.product
            deltas = []
            
            w_price_raw = float(winner.raw_values.get("price", winner.product.price_inr))
            a_price_raw = float(alt.raw_values.get("price", alt_product.price_inr))
            
            w_price = w_price_raw
            a_price = a_price_raw
            
            if w_price != a_price:
                diff = abs(w_price - a_price)
                if a_price < w_price:
                    deltas.append({
                        "attribute": "Price",
                        "description": f"{currency_symbol}{diff:,.2f} cheaper",
                        "direction": "better"
                    })
                else:
                    deltas.append({
                        "attribute": "Price",
                        "description": f"{currency_symbol}{diff:,.2f} more expensive",
                        "direction": "worse"
                    })
            
            for rule in tradeoff_config:
                if hasattr(rule, 'key'):
                    key = rule.key
                    name = rule.name
                    attr_type = rule.type
                    unit = rule.unit
                    precision = rule.precision
                    format_int = rule.format_int
                elif isinstance(rule, dict):
                    key = rule.get("key")
                    name = rule.get("name")
                    attr_type = rule.get("type")
                    unit = rule.get("unit")
                    precision = rule.get("precision")
                    format_int = rule.get("format_int")
                else:
                    continue

                w_val = winner.raw_values.get(key)
                a_val = alt.raw_values.get(key)
                if w_val is not None and a_val is not None:
                    w_val_f = float(w_val)
                    a_val_f = float(a_val)
                    if w_val_f != a_val_f:
                        diff = abs(w_val_f - a_val_f)
                        
                        if format_int:
                            diff_str = str(int(diff))
                        elif precision is not None:
                            diff_str = f"{diff:.{precision}f}"
                        else:
                            diff_str = f"{diff:.1f}"
                        
                        is_better = (a_val_f > w_val_f) if attr_type == "benefit" else (a_val_f < w_val_f)
                        
                        if is_better:
                            if attr_type == "benefit":
                                description = f"{diff_str}{unit} more {name.lower()}"
                            else:
                                description = f"{diff_str}{unit} lower {name.lower()}"
                            direction = "better"
                        else:
                            if attr_type == "benefit":
                                description = f"{diff_str}{unit} less {name.lower()}"
                            else:
                                description = f"{diff_str}{unit} higher {name.lower()}"
                            direction = "worse"
                            
                        deltas.append({
                            "attribute": name,
                            "description": description,
                            "direction": direction
                        })
            
            tradeoffs.append({
                "alternative_sku": alt_product.sku,
                "alternative_name": alt_product.name,
                "alternative_price": a_price,
                "alternative_score": float(alt.score),
                "deltas": deltas
            })
            
        return tradeoffs

    def _get_spec_val(self, product: Product, key: str) -> Optional[float]:
        """Category-configurable specs retriever with aliasing."""
        raw_val = product.specs.get(key)
        if raw_val is None:
            if key == "battery_hours":
                raw_val = product.specs.get("estimated_office_hours")
            elif key == "cpu_score":
                raw_val = product.specs.get("cpu_multi_core") or product.specs.get("processor_score")
            elif key == "gpu_score":
                raw_val = product.specs.get("gpu_score_3dmark")
        if raw_val is None:
            return None
        return DecisionEngine._safe_float(raw_val)

    def _apply_pareto_filtering(self, pool: List[Product], priorities: Dict[str, float]) -> Tuple[List[Product], Dict[str, Any]]:
        """Filters out strictly Pareto-dominated products and logs reasons."""
        pareto_attributes = []
        for attr in self.attributes:
            if attr.key == "price":
                continue
            if attr.is_hard_filter:
                # Hard filter attributes only participate if RAM/Storage
                if attr.key in ["ram_gb", "storage_gb"]:
                    pareto_attributes.append(attr)
            else:
                # Soft attributes participate if user priority >= 1.0
                if priorities.get(attr.key, 3.0) >= 1.0:
                    pareto_attributes.append(attr)

        # Performance Optimization: If pool is huge (> 250 items), pre-sort by a fast heuristic
        # to focus Pareto dominance analysis on the top candidates, preventing O(N^2) slowdown.
        if len(pool) > 250:
            # Quick spec score for pre-ranking
            def _quick_spec_score(p):
                score = 0.0
                for a in pareto_attributes:
                    val = self._get_spec_val(p, a.key)
                    if val is not None:
                        score += val if a.type == "benefit" else -val
                return score

            sorted_pool = sorted(pool, key=lambda p: (float(p.price_inr), -_quick_spec_score(p)))
            pareto_eval_pool = sorted_pool[:250]
        else:
            pareto_eval_pool = pool

        # Pre-cache spec values into memory tuples for blazing fast O(1) attribute lookup
        cached_specs = {}
        for p in pareto_eval_pool:
            cached_specs[p.sku] = (
                float(p.price_inr),
                {attr.key: (self._get_spec_val(p, attr.key), attr.type, attr.name) for attr in pareto_attributes}
            )

        dominated_products = []
        dominated_skus = set()

        for p_b in pareto_eval_pool:
            is_dominated = False
            dominator = None
            reasons = []
            price_b, specs_b = cached_specs[p_b.sku]

            for p_a in pareto_eval_pool:
                if p_a.sku == p_b.sku:
                    continue

                price_a, specs_a = cached_specs[p_a.sku]

                # 1. Price check (cost attribute: lower is better)
                if price_a > price_b:
                    continue

                equal_or_better = True
                strictly_better = False
                better_reasons = []

                if price_a < price_b:
                    strictly_better = True
                    better_reasons.append(f"cheaper (₹{price_a:,.0f} vs ₹{price_b:,.0f})")

                # 2. Check specs
                for attr_key, (val_a, attr_type, attr_name) in specs_a.items():
                    val_b = specs_b[attr_key][0]

                    if val_a is None or val_b is None:
                        equal_or_better = False
                        break

                    if attr_type == "benefit":
                        if val_a < val_b:
                            equal_or_better = False
                            break
                        elif val_a > val_b:
                            strictly_better = True
                            better_reasons.append(f"higher {attr_name} ({val_a} vs {val_b})")
                    elif attr_type == "cost":
                        if val_a > val_b:
                            equal_or_better = False
                            break
                        elif val_a < val_b:
                            strictly_better = True
                            better_reasons.append(f"lower {attr_name} ({val_a} vs {val_b})")

                if equal_or_better and strictly_better:
                    is_dominated = True
                    dominator = p_a
                    reasons = better_reasons
                    break

            if is_dominated:
                dominated_products.append({
                    "sku": p_b.sku,
                    "name": p_b.name,
                    "price": price_b,
                    "dominated_by": dominator.sku,
                    "dominated_by_name": dominator.name,
                    "dominated_by_price": float(dominator.price_inr),
                    "evidence": better_reasons,
                    "dimensions_checked": [attr.key for attr in pareto_attributes],
                    "reason": f"Dominated by {dominator.name} which is " + ", ".join(better_reasons)
                })
                dominated_skus.add(p_b.sku)

        survivors = [p for p in pool if p.sku not in dominated_skus]
        
        pareto_analysis = {
            "candidates_before": len(pool),
            "candidates_after": len(survivors),
            "dominated_products": dominated_products,
            "domination_reason": {dp["sku"]: dp["reason"] for dp in dominated_products}
        }
        
        return survivors, pareto_analysis
