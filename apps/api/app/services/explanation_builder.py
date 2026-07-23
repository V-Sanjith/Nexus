from typing import Dict, Any, List, Optional
from app.services.decision_engine import ProductScoreResult
from app.services.currency_service import CurrencyService

from pydantic import BaseModel, Field

class ExplanationEvidence(BaseModel):
    """Direction-aware evidence supporting a recommendation claim."""
    claim: str
    attribute: str
    direction: str  # "benefit" (higher is better) | "cost" (lower is better)
    winner_val: Any
    runner_val: Optional[Any] = None
    delta: Optional[float] = None
    is_supported: bool = True

class ExplanationBuilder:
    """Generates deterministic, structured explanations from Decision Engine output."""
    
    @staticmethod
    def build(
        winner: ProductScoreResult,
        alternatives: List[ProductScoreResult],
        tradeoffs: List[Dict[str, Any]],
        trace: Dict[str, Any],
        category_config: Any,
        currency_symbol: str,
        currency_code: str = "usd",
        **kwargs
    ) -> Dict[str, Any]:
        evidence_list: List[Dict[str, Any]] = []
        
        # 1. Map specs display labels/units
        spec_map = {spec.key: spec for spec in category_config.display_specs} if hasattr(category_config, 'display_specs') else {}
        if not spec_map and isinstance(category_config, dict):
            spec_map = {spec['key']: spec for spec in category_config.get('display_specs', [])}
            
        def get_label_unit(key: str) -> tuple:
            if key in spec_map:
                spec = spec_map[key]
                if hasattr(spec, 'label'):
                    return spec.label, spec.unit
                elif isinstance(spec, dict):
                    return spec.get('label', key), spec.get('unit', '')
            return key.replace('_', ' ').title(), ''

        # Spec mappings for humanized display
        def format_spec_pro(key: str, val: Any) -> Optional[str]:
            if key == "estimated_office_hours" or key == "battery_hours":
                return f"Excellent battery life of {val} hours of office/web runtime"
            elif key == "battery_capacity_wh":
                return f"High capacity {val}Wh battery for long endurance"
            elif key == "weight_kg":
                return f"Extremely lightweight and portable design at only {val}kg"
            elif key == "ram_gb":
                return f"Generous memory capacity with {val}GB RAM for multitasking"
            elif key == "storage_gb":
                return f"Ample storage capacity with {val}GB high-speed SSD space"
            elif key in ("cpu_score", "cpu_multi_core"):
                return f"High-performance processor (multi-core score: {val})"
            elif key in ("gpu_score", "gpu_score_3dmark"):
                return f"Robust graphics capabilities (3DMark score: {val})"
            elif key == "camera_mp":
                return f"High-resolution primary camera sensor of {val} MP"
            elif key == "refresh_rate_hz":
                return f"Ultra-smooth display with {val}Hz refresh rate"
            elif key == "resolution_p":
                return f"Sharp display resolution of {val}p"
            elif key in ("screen_size", "screen_size_inches"):
                return f"Immersive {val}-inch screen size"
            elif key == "color_accuracy_delta_e":
                return f"Professional-grade color accuracy with a low Delta E of {val}"
            elif key == "brightness_nits":
                return f"Bright display panel reaching up to {val} nits"
            return None

        def format_spec_con(key: str, val: Any) -> Optional[str]:
            if key == "estimated_office_hours" or key == "battery_hours":
                return f"Standard battery runtime of {val} hours under normal usage"
            elif key == "battery_capacity_wh":
                return f"Modest battery capacity of {val}Wh"
            elif key == "weight_kg":
                return f"Heavier chassis at {val}kg, which might reduce portability"
            elif key == "ram_gb":
                return f"Standard memory size of {val}GB RAM, which may limit heavy multitasking"
            elif key == "storage_gb":
                return f"Restricted storage capacity of {val}GB SSD"
            elif key in ("cpu_score", "cpu_multi_core"):
                return f"Moderate processor performance (multi-core score: {val})"
            elif key in ("gpu_score", "gpu_score_3dmark"):
                return f"Basic graphics performance (3DMark score: {val}), not ideal for heavy rendering"
            elif key == "camera_mp":
                return f"Standard camera capability of {val} MP"
            elif key == "refresh_rate_hz":
                return f"Standard display refresh rate of {val}Hz"
            elif key == "resolution_p":
                return f"Standard display resolution of {val}p"
            elif key in ("screen_size", "screen_size_inches"):
                return f"Smaller display size of {val} inches"
            elif key == "color_accuracy_delta_e":
                return f"Color deviation Delta E is {val}, which is not ideal for color-critical work"
            elif key == "brightness_nits":
                return f"Limited screen brightness of {val} nits"
            return None

        # 2. Extract factsheet data
        specs_dict = winner.product.specs or {}
        factual_pros = specs_dict.get("known_pros", [])
        factual_cons = specs_dict.get("known_cons", [])
        factual_issues = [f"Known issue: {issue}" for issue in specs_dict.get("known_issues", [])]

        # 3. Build Pros
        pros = []
        for fp in factual_pros:
            if fp not in pros:
                pros.append(fp)
                
        sorted_utilities = sorted(winner.normalized_values.items(), key=lambda x: x[1], reverse=True)
        for key, utility in sorted_utilities:
            if utility >= 0.6:
                val = winner.raw_values.get(key)
                if val is not None:
                    pro_desc = format_spec_pro(key, val)
                    if pro_desc and pro_desc not in pros:
                        pros.append(pro_desc)
        
        price_val = float(winner.raw_values.get("price", winner.product.price_inr))
        max_budget = trace.get("applied_constraints", {}).get("price_max")
        if max_budget and price_val <= max_budget * 0.85:
            local_price_val = price_val
            local_max_budget = max_budget
            pros.append(f"Highly cost-effective choice at {currency_symbol}{local_price_val:,.0f}, well within your budget limit of {currency_symbol}{local_max_budget:,.0f}")
            
        if len(pros) < 2:
            pros.append(f"Meets all your essential performance criteria")
            local_price_val = price_val
            pros.append(f"Priced competitively at {currency_symbol}{local_price_val:,.0f}")
            
        pros = pros[:3]

        # Build Cons
        cons = []
        for fc in factual_cons:
            if fc not in cons:
                cons.append(fc)
        for fi in factual_issues:
            if fi not in cons:
                cons.append(fi)
                
        sorted_cons = sorted(winner.normalized_values.items(), key=lambda x: x[1])
        for key, utility in sorted_cons:
            if utility < 0.4:
                val = winner.raw_values.get(key)
                if val is not None:
                    con_desc = format_spec_con(key, val)
                    if con_desc and con_desc not in cons:
                        cons.append(con_desc)
        
        if max_budget and price_val >= max_budget * 0.95:
            cons.append(f"Consumes almost the entirety of your specified budget limit")
            
        if not cons:
            cons.append("Slightly premium price point compared to entry-level alternatives")
            
        cons = cons[:2]

        # 4. Build Rejections breakdown
        rejection_summary = ""
        catalog_filtered = trace.get("catalog_filtered_out", [])
        rejections = trace.get("rejections", {})
        rejections_by_reason = trace.get("rejections_by_reason", {})
        
        num_subtype_filtered = len(catalog_filtered)
        num_rejected = len(rejections)
        
        if num_subtype_filtered > 0 or num_rejected > 0:
            rejection_parts = []
            if num_subtype_filtered > 0:
                rejection_parts.append(f"{num_subtype_filtered} products that do not match the required subtype or category filters")
            
            reason_details = []
            for r_key, r_count in rejections_by_reason.items():
                label, _ = get_label_unit(r_key)
                reason_details.append(f"{r_count} failed {label} constraint")
                
            if reason_details:
                rejection_parts.append(f"{num_rejected} products filtered by compatibility rules ({', '.join(reason_details)})")
                
            rejection_summary = f"To find the best matches, the engine analyzed the database catalog and excluded: {'; '.join(rejection_parts)}."

        # 5. Format special "No Match Found" layout if triggered
        is_no_match = (trace.get("status") == "no_match_found")
        
        if is_no_match:
            display_name = category_config.display_name if hasattr(category_config, 'display_name') else category_config.get('display_name', 'Products')
            summary = f"No {display_name.lower()} satisfies all your strict constraints. Here are the closest candidates."
            
            paragraphs = [
                f"### No Match Found\n\nThe Nexus decision engine analyzed the available catalog but could not find a product that satisfies all of your strict constraints.",
                rejection_summary,
                "#### Closest Matches\n\nHere are the top candidates that failed your constraints by the smallest margin:"
            ]
            
            closest_list = []
            for item in trace.get("closest_matches", []):
                price_converted = item["price"]
                reason_failed = item.get("reason_failed", "failed constraint checks")
                closest_list.append(f"- **{item['name']}** ({currency_symbol}{price_converted:,.0f}): {reason_failed.capitalize()}")
                
            paragraphs.append("\n".join(closest_list))
            paragraphs.append(
                "If none of these candidates are acceptable, please consider relaxing your budget limits, "
                "reducing your RAM/storage constraints, or adjusting your portability requirements."
            )
            
            reasoning = "\n\n".join(paragraphs)
            
            return {
                "verdict_sku": winner.product.sku,
                "score": float(winner.score),
                "confidence": float(winner.confidence_score),
                "pros": pros,
                "cons": cons,
                "reasoning": reasoning,
                "summary": summary,
                "citations": [
                    "Nexus Catalog Filtering & Compliance Trace Log",
                    "Database SKU Specifications"
                ]
            }

        # 6. Normal recommendation path
        local_price_val = price_val
        
        import re
        def normalize_spec_text(text: str) -> str:
            if not text: return text
            replacements = [
                ("2k", "2K"), ("4k", "4K"), ("1080p", "1080p"), ("1440p", "1440p"), ("2160p", "2160p"),
                ("120hz", "120Hz"), ("144hz", "144Hz"), ("165hz", "165Hz"), ("240hz", "240Hz"), ("360hz", "360Hz"), ("60hz", "60Hz"),
                ("snapdragon 8 gen 3", "Snapdragon 8 Gen 3"), ("snapdragon 8 gen 2", "Snapdragon 8 Gen 2"),
                ("5400mah", "5400mAh"), ("5000mah", "5000mAh"), ("4500mah", "4500mAh"),
                ("100w", "100W"), ("65w", "65W"), ("80w", "80W"), ("33w", "33W"), ("45w", "45W")
            ]
            res = text
            for old_val, new_val in replacements:
                res = re.sub(r'(?i)\b' + re.escape(old_val) + r'\b', new_val, res)
            # Remove decimal cents from prices like ₹52,812.03 -> ₹52,812
            res = re.sub(r'₹(\d{1,3}(?:,\d{3})*)\.\d{2}', r'₹\1', res)
            return res

        # Humanize the top pros for the summary
        pros_summary_str = ""
        if len(pros) > 0:
            # Clean up descriptions for inline reading
            clean_pros = [normalize_spec_text(p.split(" (scored")[0]) for p in pros]
            if len(clean_pros) == 1:
                pros_summary_str = f" due to its {clean_pros[0]}"
            elif len(clean_pros) > 1:
                pros_summary_str = f" because of its {', '.join(clean_pros[:-1])} and {clean_pros[-1]}"

        summary = (
            f"Based on your preferences, the {winner.product.name} is your best overall match. "
            f"Priced at {currency_symbol}{int(round(local_price_val)):,}, it satisfies all your critical constraints{pros_summary_str}."
        )
        summary = normalize_spec_text(summary)

        persona = trace.get("applied_persona", "general").title()
        confidence = winner.confidence_score
        
        # Build clean reasoning
        reasoning_parts = [
            f"After analyzing your query and comparing all available options, the **{winner.product.name}** emerged as the top recommendation. "
            f"It aligns perfectly with your requirements as a **{persona}** user, offering the best overall balance of performance, features, and price."
        ]

        # Highlight key strengths in reasoning
        if pros:
            strengths_text = "Key highlights that make this product stand out include:\n"
            for pro in pros:
                strengths_text += f"- {pro}\n"
            reasoning_parts.append(strengths_text)

        # Explain why it was chosen over others in plain English
        rejection_note = ""
        if rejection_summary:
            rejection_note = f" In compiling these results, the engine analyzed the catalog and excluded {rejection_summary.split('excluded: ')[1]}"

        reasoning_parts.append(
            f"This product was chosen because it delivers the most optimal trade-offs for your budget. "
            f"It maximizes your most important specifications without exceeding your budget limit.{rejection_note} "
            f"We are **{confidence:.1f}%** confident in this recommendation based on how closely its specifications align with your stated priorities."
        )
        
        if trace.get("status") == "relaxed_constraints":
            relaxation_steps = "; ".join(trace.get("relaxation_log", []))
            reasoning_parts.append(
                f"Note: Some of your original strict constraints could not be satisfied simultaneously. "
                f"The system automatically relaxed constraints ({relaxation_steps}) to discover this recommendation."
            )

        reasoning = normalize_spec_text("\n\n".join(reasoning_parts))

        # Populate direction-aware evidence
        for pro in pros:
            evidence_list.append({
                "claim": pro,
                "attribute": "spec_match",
                "direction": "benefit",
                "winner_val": winner.product.name,
                "is_supported": True
            })

        return {
            "verdict_sku": winner.product.sku,
            "score": float(winner.score),
            "confidence": float(confidence),
            "pros": pros,
            "cons": cons,
            "evidence": evidence_list,
            "reasoning": reasoning,
            "summary": summary,
            "citations": [
                "Nexus Decision Engine Math Calculations",
                f"{winner.product.name} Verified Product Specifications"
            ]
        }

    @staticmethod
    def build_no_match(
        closest_matches: List[Dict[str, Any]],
        trace: Dict[str, Any],
        category_config: Any,
        currency_symbol: str,
        currency_code: str = "usd"
    ) -> Dict[str, Any]:
        """
        Generates structured explanations and relaxation suggestions when no products match.
        """
        suggestions = []
        summary = "We couldn't find any products that match all of your requirements. Here are the closest matches and suggestions on how you can relax your constraints to find a match."
        
        if closest_matches:
            best_match = closest_matches[0]
            failed_checks = [c for c in best_match.get("checks", []) if c.get("status") == "fail"]
            
            applied_constraints = trace.get("applied_constraints", {})
            from app.services.currency_service import CurrencyService
            
            for check in failed_checks:
                key = check["key"]
                label = check["label"]
                
                limit_usd = None
                if f"{key}_max" in applied_constraints:
                    limit_usd = applied_constraints[f"{key}_max"]
                elif f"{key}_min" in applied_constraints:
                    limit_usd = applied_constraints[f"{key}_min"]
                elif f"{key}_eq" in applied_constraints:
                    limit_usd = applied_constraints[f"{key}_eq"]
                    
                current_val_str = ""
                if limit_usd is not None:
                    if key == "price":
                        limit_local = CurrencyService.convert_from_usd(float(limit_usd), currency_code)
                        current_val_str = f"{currency_symbol}{limit_local:,.0f}"
                    else:
                        spec_config = next((s for s in getattr(category_config, 'display_specs', []) if s.key == key), None)
                        if not spec_config and isinstance(category_config, dict):
                            spec_config = next((s for s in category_config.get('display_specs', []) if s.get('key') == key), None)
                        unit = ""
                        if spec_config:
                            unit = getattr(spec_config, 'unit', '') if hasattr(spec_config, 'unit') else spec_config.get('unit', '')
                        
                        if isinstance(limit_usd, (int, float)):
                            current_val_str = f"{int(round(limit_usd))} {unit}".strip() if key in ["ram_gb", "storage_gb", "refresh_rate_hz", "battery_hours", "camera_mp", "battery_mah"] else f"{limit_usd:g} {unit}".strip()
                        else:
                            current_val_str = str(limit_usd)
                else:
                    current_val_str = "Selected requirement"
                    
                suggestions.append({
                    "constraint": key,
                    "label": label,
                    "current": current_val_str,
                    "recommended": check["value"]
                })
            
            failed_labels = [s["label"].lower() for s in suggestions]
            if len(failed_labels) == 1:
                reasoning = f"No product met all your criteria, primarily due to your {failed_labels[0]} constraint. The closest option is the **{best_match['name']}**, which matches your preferences but requires relaxing your {failed_labels[0]} slightly (e.g., to {suggestions[0]['recommended']})."
            elif len(failed_labels) > 1:
                reasoning = f"No products satisfied all your filters simultaneously. The closest candidate is the **{best_match['name']}**, which would require adjusting your requirements for {', '.join(failed_labels[:-1])} and {failed_labels[-1]}."
            else:
                reasoning = f"No products met all your criteria. The closest option in the catalog is the **{best_match['name']}** at {currency_symbol}{best_match['price']:,.0f}."
        else:
            reasoning = "We were unable to find any products in the catalog that are within the allowed relaxation limits for your constraints. Please consider raising your budget or lowering your hardware requirements."
            
        return {
            "pros": [],
            "cons": [],
            "tradeoffs": [],
            "citations": [],
            "summary": summary,
            "reasoning": reasoning,
            "suggestions": suggestions
        }

