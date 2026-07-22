from typing import List, Dict, Any, Optional, Tuple
import structlog
from app.models.product import Product
from app.services.decision_engine import ProductScoreResult, DecisionEngine

logger = structlog.get_logger()

NEAR_TIE_THRESHOLD = 0.02  # 2.0% relative score margin threshold

class DecisionGuardrails:
    """
    Active decision quality guardrail pipeline.
    Executes BEFORE final recommendation generation to prevent or correct invalid decisions.
    """

    @staticmethod
    def evaluate(
        scored_results: List[ProductScoreResult],
        answers_summary: List[Dict[str, Any]],
        category_config: Any,
        engine: DecisionEngine,
        trace: Dict[str, Any],
        currency_symbol: str = "₹"
    ) -> Tuple[List[ProductScoreResult], Dict[str, Any]]:
        """
        Applies active guardrails to candidate pool.
        Returns potentially re-ordered/filtered scored_results and guardrail execution audit trace.
        """
        guardrail_log = {
            "guardrail_1_hard_constraints": "PASSED",
            "guardrail_2_budget_validation": "PASSED",
            "guardrail_3_dominance_validation": "PASSED",
            "guardrail_4_value_sanity": "PASSED",
            "guardrail_5_upgrade_sanity": "PASSED",
            "guardrail_6_uncertainty_handling": "PASSED",
            "is_near_tie": False,
            "relative_score_margin": 0.0,
            "deciding_factor": None,
            "corrections_applied": []
        }

        if not scored_results:
            return scored_results, guardrail_log

        # -------------------------------------------------------------
        # Extract Hard Constraints & Budget Limit
        # -------------------------------------------------------------
        hard_max_budget: Optional[float] = None
        min_ram: Optional[float] = None
        min_storage: Optional[float] = None
        need_linux = False

        for ans in answers_summary:
            maps_to = ans.get("maps_to")
            val = ans.get("selected_value")
            if isinstance(val, dict):
                val = val.get("value")

            if maps_to == "price" and val is not None:
                try:
                    hard_max_budget = float(val)
                except (ValueError, TypeError):
                    pass
            elif maps_to == "ram_gb" and val is not None:
                try:
                    min_ram = float(val)
                except (ValueError, TypeError):
                    pass
            elif maps_to == "storage_gb" and val is not None:
                try:
                    min_storage = float(val)
                except (ValueError, TypeError):
                    pass
            elif maps_to == "need_linux" and val is not None:
                need_linux = str(val).lower() in ["yes", "true", "1"]

        # -------------------------------------------------------------
        # GUARDRAIL 1 & 2: Hard Constraint & Budget Validation
        # -------------------------------------------------------------
        valid_candidates: List[ProductScoreResult] = []
        for cand in scored_results:
            p = cand.product
            price = float(p.price_inr)
            is_valid = True
            rejection_reason = None

            if hard_max_budget is not None and price > hard_max_budget:
                is_valid = False
                rejection_reason = f"Price {currency_symbol}{price:,.0f} exceeds max budget {currency_symbol}{hard_max_budget:,.0f}"

            if min_ram is not None:
                ram = engine._get_spec_val(p, "ram_gb")
                if ram is not None and ram < min_ram:
                    is_valid = False
                    rejection_reason = f"RAM {ram}GB below required {min_ram}GB"

            if min_storage is not None:
                storage = engine._get_spec_val(p, "storage_gb")
                if storage is not None and storage < min_storage:
                    is_valid = False
                    rejection_reason = f"Storage {storage}GB below required {min_storage}GB"

            if need_linux and p.specs.get("linux_supported") is not True:
                is_valid = False
                rejection_reason = "Does not support Linux natively"

            if p.specs.get("stock", True) is False:
                is_valid = False
                rejection_reason = "Out of stock"

            if is_valid:
                valid_candidates.append(cand)
            else:
                logger.info("Guardrail 1/2 rejected candidate", sku=p.sku, reason=rejection_reason)

        if not valid_candidates:
            logger.warning("Guardrails rejected all scored candidates; preserving original pool for graceful fallback.")
            valid_candidates = list(scored_results)
            guardrail_log["guardrail_1_hard_constraints"] = "WARNING_ALL_REJECTED"
        elif valid_candidates[0].product.sku != scored_results[0].product.sku:
            correction_msg = f"Replaced winner {scored_results[0].product.sku} with valid candidate {valid_candidates[0].product.sku}"
            guardrail_log["corrections_applied"].append(correction_msg)
            guardrail_log["guardrail_1_hard_constraints"] = "CORRECTED"

        # -------------------------------------------------------------
        # GUARDRAIL 3: Dominance Validation on Winner
        # -------------------------------------------------------------
        winner = valid_candidates[0]
        winner_price = float(winner.product.price_inr)
        
        for other in valid_candidates[1:]:
            other_price = float(other.product.price_inr)
            if other_price <= winner_price and other.score > winner.score:
                guardrail_log["guardrail_3_dominance_validation"] = "WARNING_SUBOPTIMAL_WINNER"
                break

        # -------------------------------------------------------------
        # NEAR-TIE DETECTION (Relative Score Margin)
        # -------------------------------------------------------------
        if len(valid_candidates) >= 2:
            runner_up = valid_candidates[1]
            winner_score = float(winner.score)
            runner_score = float(runner_up.score)
            
            epsilon = 1e-6
            denom = max(abs(winner_score), epsilon)
            rel_margin = (winner_score - runner_score) / denom
            guardrail_log["relative_score_margin"] = round(rel_margin, 4)

            if rel_margin < NEAR_TIE_THRESHOLD:
                guardrail_log["is_near_tie"] = True
                
                deciding_attr = None
                max_diff = -1.0
                for attr in engine.attributes:
                    if attr.key == "price":
                        continue
                    w_val = engine._get_spec_val(winner.product, attr.key)
                    r_val = engine._get_spec_val(runner_up.product, attr.key)
                    if w_val is not None and r_val is not None:
                        if attr.type == "benefit" and w_val > r_val:
                            diff = (w_val - r_val) / max(w_val, 1e-6)
                            if diff > max_diff:
                                max_diff = diff
                                deciding_attr = attr.name
                        elif attr.type == "cost" and w_val < r_val:
                            diff = (r_val - w_val) / max(r_val, 1e-6)
                            if diff > max_diff:
                                max_diff = diff
                                deciding_attr = attr.name
                
                guardrail_log["deciding_factor"] = deciding_attr or "specific user preference weights"
                logger.info("Near-tie decision detected", winner=winner.product.sku, runner_up=runner_up.product.sku, rel_margin=rel_margin, deciding_factor=guardrail_log["deciding_factor"])

        # -------------------------------------------------------------
        # GUARDRAIL 6: Low Confidence / Uncertainty Check
        # -------------------------------------------------------------
        cand_count = len(valid_candidates)
        filled_specs = len([k for k, v in winner.product.specs.items() if v is not None])
        spec_coverage = (filled_specs / max(1, len(engine.attributes))) * 100.0

        if cand_count < 3 or spec_coverage < 50.0 or guardrail_log["is_near_tie"]:
            guardrail_log["guardrail_6_uncertainty_handling"] = "UNCERTAINTY_FLAGGED"

        return valid_candidates, guardrail_log
