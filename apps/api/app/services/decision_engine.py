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
        if "phone" in q or "smartphone" in q or "mobile" in q:
            category = "smartphone"
        elif "monitor" in q or "display" in q or "screen" in q:
            category = "monitor"
        elif "laptop" in q or "notebook" in q or "macbook" in q:
            category = "laptop"
            
        # 2. Detect Subtype
        subtype = default_subtype
        if "gaming" in q or "gamer" in q:
            subtype = "gaming"
        elif "business" in q or "work" in q or "office" in q:
            subtype = "business"
        elif "creator" in q or "editing" in q or "design" in q:
            subtype = "creator"
        elif "programming" in q or "developer" in q or "coding" in q:
            subtype = "developer"
        elif "photo" in q or "camera" in q:
            subtype = "photography"
        elif "foldable" in q:
            subtype = "foldable"
            
        # 3. Detect Budget (e.g. ₹100000, 100k, rs 60000, rs. 60k, 40k)
        budget = None
        # Match 'k' suffix e.g. 40k, 100k
        match_k = re.search(r'(\d+)\s*k\b', q)
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
                priorities[maps_to] = float(val_f)

        # Determine budget in local currency and convert to USD
        local_budget = detected_budget
        if local_budget is None:
            # Fallback to answers
            local_budget = user_pref.get("price")

        # Determine if query uses INR
        is_inr = "₹" in raw_query or "rs" in raw_query.lower() or "inr" in raw_query.lower() or currency_code == "inr"
        
        budget_inr = None
        if local_budget is not None:
            if is_inr:
                budget_inr = CurrencyService.convert_to_usd(local_budget, "inr")
            else:
                budget_inr = CurrencyService.convert_to_usd(local_budget, currency_code)

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
                if sub == "design":
                    return "designer"
                if sub == "professional":
                    return "productivity"
                return sub
            return "general"

        # A. Subtype Filter
        subtype_filtered = []
        for p in current_pool:
            p_sub = get_product_subtype(p)
            if detected_subtype == "general" or p_sub == detected_subtype:
                subtype_filtered.append(p)
        
        current_pool = subtype_filtered
        stage5_trace.append(("Subtype", len(current_pool)))

        # B. GPU Filter (For Gaming Laptops only)
        gpu_filtered = []
        for p in current_pool:
            if p.category == "laptop" and detected_subtype == "gaming":
                if p.specs.get("gpu_type") == "dedicated":
                    gpu_filtered.append(p)
            else:
                gpu_filtered.append(p)
                
        current_pool = gpu_filtered
        stage5_trace.append(("GPU", len(current_pool)))

        # C. Budget Filter (Two-Tier: Prefer products within 20% of budget, fallback to full budget if none exist)
        budget_filtered = []
        rejections = {}
        rejections_by_reason = {}
        
        if budget_inr is not None:
            # Tier 1: Try to find products in [0.8 * budget_inr, budget_inr]
            tier1_pool = []
            lower_bound = budget_inr * 0.80
            for p in current_pool:
                p_price = float(p.price_inr)
                if lower_bound <= p_price <= (budget_inr + 0.01):
                    tier1_pool.append(p)
            
            if tier1_pool:
                # Products exist in the preferred 20% budget window
                for p in current_pool:
                    p_price = float(p.price_inr)
                    if p_price < lower_bound:
                        rejections[p.sku] = f"Price {currency_symbol}{p_price:,.0f} is below the preferred 20% budget window of {currency_symbol}{lower_bound:,.0f}"
                    elif p_price > (budget_inr + 0.01):
                        rejections[p.sku] = f"Price {currency_symbol}{p_price:,.0f} exceeded maximum budget of {currency_symbol}{budget_inr:,.0f}"
                budget_filtered = tier1_pool
            else:
                # Tier 2 Fallback: Use all products <= budget_inr
                for p in current_pool:
                    p_price = float(p.price_inr)
                    if p_price <= (budget_inr + 0.01):
                        budget_filtered.append(p)
                    else:
                        rejections[p.sku] = f"Price {currency_symbol}{p_price:,.0f} exceeded maximum budget of {currency_symbol}{budget_inr:,.0f}"
        else:
            budget_filtered = list(current_pool)
            
        current_pool = budget_filtered
        stage5_trace.append(("Budget", len(current_pool)))

        # D. Stock Filter
        stock_filtered = []
        for p in current_pool:
            if p.specs.get("stock", True):
                stock_filtered.append(p)
                
        current_pool = stock_filtered
        stage5_trace.append(("Stock", len(current_pool)))

        # E. Generic Hard Filters (RAM, Storage, etc. based on config)
        generic_filtered = []
        for p in current_pool:
            keep = True
            for attr in self.attributes:
                if attr.key == "price":
                    continue  # Handled separately in Budget Filter
                if attr.is_hard_filter and attr.key in user_pref:
                    pref_val = user_pref[attr.key]
                    # Map aliases if needed
                    raw_val = p.specs.get(attr.key)
                    if raw_val is None:
                        if attr.key == "battery_hours":
                            raw_val = p.specs.get("estimated_office_hours")
                        elif attr.key == "cpu_score":
                            raw_val = p.specs.get("cpu_multi_core") or p.specs.get("processor_score")
                        elif attr.key == "gpu_score":
                            raw_val = p.specs.get("gpu_score_3dmark")
                    
                    if raw_val is not None:
                        spec_val_f = DecisionEngine._safe_float(raw_val)
                        if attr.type == "benefit":
                            if spec_val_f < pref_val:
                                keep = False
                                rejections[p.sku] = f"{attr.name} {raw_val} is below the required minimum of {pref_val}"
                                break
                        else:  # cost
                            if spec_val_f > pref_val:
                                keep = False
                                rejections[p.sku] = f"{attr.name} {raw_val} exceeded the allowed maximum of {pref_val}"
                                break
            if keep:
                generic_filtered.append(p)
                
        current_pool = generic_filtered
        stage5_trace.append(("GenericHardFilters", len(current_pool)))

        # Log pipeline trace counts
        pipeline_trace_log = {
            "Loaded": len(stage4_output),
            "Subtype": stage5_trace[0][1],
            "GPU": stage5_trace[1][1],
            "Budget": stage5_trace[2][1],
            "Stock": stage5_trace[3][1],
            "GenericHardFilters": stage5_trace[4][1],
        }
        
        # Log to stdout as requested:
        print(f"\n[Pipeline Trace for '{raw_query}']")
        print(f"  Loaded  -> {pipeline_trace_log['Loaded']}")
        print(f"  Subtype -> {pipeline_trace_log['Subtype']}")
        print(f"  GPU     -> {pipeline_trace_log['GPU']}")
        print(f"  Budget  -> {pipeline_trace_log['Budget']}")
        print(f"  Stock   -> {pipeline_trace_log['Stock']}")

        trace = {
            "applied_constraints": {"price_max": budget_inr} if budget_inr is not None else {},
            "catalog_filtered_out": [],
            "rejections": rejections,
            "rejections_by_reason": {"price": len(rejections)} if rejections else {},
            "normalized_weights": {},
            "scoring_breakdown": {},
            "ranking": [],
            "status": "success",
            "closest_matches": [],
            "pipeline_trace": [
                {"stage": 1, "name": "User Query", "count": 1},
                {"stage": 2, "name": "Intent Detection", "count": 1},
                {"stage": 3, "name": "Category Detection", "count": len(stage3_output)},
                {"stage": 4, "name": "Catalog Loading", "count": len(stage4_output)},
                {"stage": 5, "name": "Hard Filters", "details": pipeline_trace_log}
            ]
        }

        # If 0 products remain after hard filtering, stop immediately and return closest matches diagnostics
        if len(current_pool) == 0:
            print("  Winner  -> No Match")
            trace["status"] = "no_match_found"
            
            # Find closest matches from the category pool (excluding budget)
            closest_candidates = []
            for p in stage3_output:
                p_price = float(p.price_inr)
                checks = []
                total_distance = 0.0
                
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
                
            return [], trace, "no_match_found"

        # ---------------------------------------------------------
        # STAGE 6: Soft Scoring (MCDA)
        # ---------------------------------------------------------
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

        # Establish boundaries for normalization (using only surviving products)
        boundaries: Dict[str, Dict[str, float]] = {}
        soft_attributes = [a for a in self.attributes if not a.is_hard_filter]
        
        for attr in soft_attributes:
            vals = []
            for p in current_pool:
                calculated_scores = ScoreCalculator.calculate_all(self.category, p.specs, float(p.price_inr))
                
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

        # Calculate utility scores
        mcda_results = []
        for p in current_pool:
            scoring_breakdown: Dict[str, float] = {}
            normalized_values: Dict[str, float] = {}
            
            calculated_scores = ScoreCalculator.calculate_all(self.category, p.specs, float(p.price_inr))
            raw_values = {"price": float(p.price_inr)}
            for k, v in p.specs.items():
                raw_values[k] = v
            for k, v in calculated_scores.items():
                raw_values[k] = v
                
            # Apply key aliasing
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
                    else:  # cost
                        norm_val = (v_max - val) / (v_max - v_min)
                        
                normalized_values[attr.key] = norm_val
                weighted_val = norm_val * normalized_weights.get(attr.key, 0.0)
                scoring_breakdown[attr.key] = weighted_val
                base_utility += weighted_val
                
            mcda_results.append(ProductScoreResult(
                product=p,
                score=base_utility,
                confidence_score=90.0,
                scoring_breakdown=scoring_breakdown,
                normalized_values=normalized_values,
                raw_values=raw_values
            ))
            
        # ---------------------------------------------------------
        # STAGE 7: Ranking
        # ---------------------------------------------------------
        # Sort initial MCDA results
        mcda_results.sort(key=lambda x: (-x.score, float(x.product.price_inr)))

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

        # Apply diversity penalty
        diverse_results: List[ProductScoreResult] = []
        for candidate in mcda_results:
            penalty = 0.0
            for selected in diverse_results:
                sim = self._calculate_similarity(candidate, selected)
                if sim > 0.70:
                    penalty += 0.20 * (sim - 0.70)
            candidate.score -= penalty
            diverse_results.append(candidate)
            
        # Final Sort after diversity penalty
        diverse_results.sort(key=lambda x: (-x.score, float(x.product.price_inr), -x.confidence_score))

        # Populate trace ranking logs
        for idx, res in enumerate(diverse_results):
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

        winner = diverse_results[0].product
        print(f"  MCDA    -> {len(diverse_results)}")
        print(f"  Winner  -> {winner.name}\n")

        # ---------------------------------------------------------
        # STAGE 8: Explanation
        # ---------------------------------------------------------
        # Handled downstream in RecommendationService via ExplanationBuilder
        return diverse_results, trace, "success"

    def _infer_persona(self, hard_filters: Dict[str, Any], priorities: Dict[str, float]) -> str:
        """Heuristically determines user persona based on priority sliders and budget constraints."""
        category_name = self.category
        if category_name == "laptop":
            scores = {"gamer": 0, "developer": 0, "video editor": 0, "traveller": 0, "student": 0, "business user": 0}
            budget = hard_filters.get("price", {}).get("max")
            if budget and (budget <= 80000.0 if budget > 10000 else budget <= 1000.0):
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
            camera = priorities.get("camera_mp", 3.0)
            gaming = priorities.get("processor_score", 3.0)
            battery = priorities.get("battery_mah", 3.0)
            
            if camera >= 4.0:
                scores["photographer"] += 3
            if gaming >= 4.0:
                scores["gamer"] += 3
            if battery >= 4.0:
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

        return 0.5 * spec_sim + 0.5 * use_case_sim

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
