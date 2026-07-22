from typing import Dict, Any, List, Optional, Tuple
import structlog

logger = structlog.get_logger()

class DecisionInvariantAuditor:
    """
    Read-only decision invariant auditor.
    Inspects finalized recommendation payload, reports consistency violations,
    and attaches diagnostic audit status. NEVER modifies the recommendation.
    """

    @staticmethod
    def audit(
        recommendation_payload: Dict[str, Any],
        structured_analysis: Dict[str, Any],
        engine: Any = None,
        category_config: Any = None
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """
        Runs read-only checks on finalized recommendation payload.
        Returns Tuple[audit_status ("PASSED" | "VIOLATION_DETECTED"), violations_list].
        """
        violations: List[Dict[str, Any]] = []

        winner = recommendation_payload.get("verdict_product")
        winner_price = winner.get("price") if winner else None
        winner_score = recommendation_payload.get("score") or recommendation_payload.get("confidence")

        spend_less = structured_analysis.get("spend_less_analysis")
        upgrade = structured_analysis.get("upgrade_analysis")
        tradeoffs = structured_analysis.get("tradeoffs") or []
        sensitivity = structured_analysis.get("sensitivity_analysis") or []
        pareto = structured_analysis.get("decision_trace", {}).get("pareto_analysis") or {}

        # -------------------------------------------------------------
        # Invariant 1: winner_not_dominated_by_cheaper
        # -------------------------------------------------------------
        if spend_less and winner_score:
            sl_retained_pct = spend_less.get("retained_utility_percentage", 0.0)
            if sl_retained_pct > 100.0:
                violations.append({
                    "invariant": "winner_not_dominated_by_cheaper",
                    "severity": "HIGH",
                    "reason": f"Spend Less candidate {spend_less.get('sku')} has higher utility ({sl_retained_pct:.1f}%) than winner"
                })

        # -------------------------------------------------------------
        # Invariant 2: runner_up_score_order
        # -------------------------------------------------------------
        battle = structured_analysis.get("battle_comparison")
        if battle:
            w_score = battle.get("winner_score", 0.0)
            r_score = battle.get("runner_score", 0.0)
            if r_score > w_score:
                violations.append({
                    "invariant": "runner_up_score_order",
                    "severity": "CRITICAL",
                    "reason": f"Runner-up score ({r_score}) exceeds winner score ({w_score})"
                })

        # -------------------------------------------------------------
        # Invariant 3: upgrade_price_greater
        # -------------------------------------------------------------
        if upgrade and winner_price:
            up_price = upgrade.get("price", 0.0)
            if up_price <= winner_price:
                violations.append({
                    "invariant": "upgrade_price_greater",
                    "severity": "HIGH",
                    "reason": f"Upgrade price ({up_price}) is not strictly greater than winner price ({winner_price})"
                })

        # -------------------------------------------------------------
        # Invariant 5: upgrade_meaningful_improvement
        # -------------------------------------------------------------
        if upgrade:
            gain_pct = upgrade.get("percentage_utility_gain", 0.0)
            gains = upgrade.get("gains", [])
            if gain_pct < 0.0 or not gains:
                violations.append({
                    "invariant": "upgrade_meaningful_improvement",
                    "severity": "MEDIUM",
                    "reason": f"Upgrade candidate {upgrade.get('sku')} offers negative or zero utility gain ({gain_pct:.1f}%)"
                })

        # -------------------------------------------------------------
        # Invariant 6: pareto_elimination_validity
        # -------------------------------------------------------------
        dominated_list = pareto.get("dominated_products") or []
        for dp in dominated_list:
            if not dp.get("dominated_by") or not dp.get("evidence"):
                violations.append({
                    "invariant": "pareto_elimination_validity",
                    "severity": "HIGH",
                    "reason": f"Pareto-eliminated product {dp.get('sku')} missing dominating product or evidence"
                })

        # -------------------------------------------------------------
        # Invariant 7: sensitivity_winner_distinct
        # -------------------------------------------------------------
        if winner:
            winner_sku = winner.get("sku")
            for trigger in sensitivity:
                alt_sku = trigger.get("alternative_winner_sku")
                if alt_sku == winner_sku:
                    violations.append({
                        "invariant": "sensitivity_winner_distinct",
                        "severity": "HIGH",
                        "reason": f"Sensitivity analysis reported current winner {winner_sku} as alternative winner"
                    })

        # -------------------------------------------------------------
        # Invariant 9: best_for_avoid_consistency
        # -------------------------------------------------------------
        pros = structured_analysis.get("pros") or []
        cons = structured_analysis.get("cons") or []
        pros_str = " ".join(pros).lower()
        cons_str = " ".join(cons).lower()

        if "excellent battery" in pros_str and "poor battery" in cons_str:
            violations.append({
                "invariant": "best_for_avoid_consistency",
                "severity": "HIGH",
                "reason": "Pros claim excellent battery while Cons claim poor battery"
            })
        if "lightweight" in pros_str and "heavy" in cons_str:
            violations.append({
                "invariant": "best_for_avoid_consistency",
                "severity": "HIGH",
                "reason": "Pros claim lightweight while Cons claim heavy"
            })

        # -------------------------------------------------------------
        # Invariant 12: score_consistency
        # -------------------------------------------------------------
        score_val = recommendation_payload.get("score")
        conf_val = recommendation_payload.get("confidence")
        if score_val is not None and conf_val is not None and abs(float(score_val) - float(conf_val)) > 1e-4:
            violations.append({
                "invariant": "score_consistency",
                "severity": "MEDIUM",
                "reason": f"Score ({score_val}) and Confidence ({conf_val}) do not match"
            })

        audit_status = "PASSED" if not violations else "VIOLATION_DETECTED"
        if violations:
            logger.warning("DecisionInvariantAuditor detected violations", count=len(violations), status=audit_status)

        return audit_status, violations
