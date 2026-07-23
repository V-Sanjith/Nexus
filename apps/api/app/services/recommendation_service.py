import asyncio
from uuid import UUID
from typing import Optional, Dict, Any, List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.repositories.decision_repo_impl import SQLAlchemyDecisionRepository
from app.repositories.recommendation_repo_impl import SQLAlchemyRecommendationRepository
from app.services.decision_engine import DecisionEngine
from app.services.currency_service import CurrencyService
from app.services.category_registry import CategoryRegistry
from app.services.explanation_builder import ExplanationBuilder
from app.services.catalog_provider import LocalCatalogProvider
from app.models.recommendation import Recommendation, RecommendationVersion
from app.models.product import Product
from app.services.decision_guardrails import DecisionGuardrails
from app.services.decision_auditor import DecisionInvariantAuditor
import structlog

logger = structlog.get_logger()

class RecommendationService:
    """Orchestrates decision scoring, catalog querying, and dynamic explanations generation."""

    # In-memory lock registry to serialize concurrent requests for the same decision
    _locks: Dict[UUID, asyncio.Lock] = {}

    def __init__(self, session: AsyncSession):
        self.session = session
        self.decision_repo = SQLAlchemyDecisionRepository(session)
        self.recommendation_repo = SQLAlchemyRecommendationRepository(session)


    async def generate_recommendation(self, decision_id: UUID) -> Recommendation:
        """
        Runs the independent stages of the recommendation pipeline:
        1. Query answers & convert currencies.
        2. Query the CatalogProvider interface.
        3. Match config-driven subtype filters and compatibility rules.
        4. Calculate dynamic specs suitability scores.
        5. Perform MCDA ranking.
        6. Apply catalog confidence score formula.
        7. Generate spec-driven dynamic explanations.
        8. Log rejections and closest matches on constraint failures.
        """
        # Get or create a lock for this specific decision_id to serialize concurrent requests
        lock = RecommendationService._locks.setdefault(decision_id, asyncio.Lock())
        
        async with lock:
            try:
                return await self._generate_recommendation_internal(decision_id)
            finally:
                # Clean up the lock to prevent memory leaks
                RecommendationService._locks.pop(decision_id, None)

    @staticmethod
    def _determine_image_provenance(product: Any) -> Dict[str, str]:
        if not product:
            return {"image_url": "/images/image-unavailable.svg", "image_source": "placeholder", "image_match_level": "unavailable"}
        
        match_level = getattr(product, "image_match_level", None) or "unverified"
        specs = getattr(product, "specs", {}) or {}
        img = getattr(product, "image_url", None) or specs.get("image_url")
        
        if not img or not str(img).startswith("http") or "placeholder" in str(img).lower():
            return {"image_url": "/images/image-unavailable.svg", "image_source": "placeholder", "image_match_level": "unavailable"}

        p_name = str(getattr(product, "name", "")).lower()
        p_brand = str(getattr(product, "brand", "") or specs.get("brand", "")).lower()

        # Reject generic iPhone stock photo for non-Apple products
        if "photo-1511707171634" in str(img):
            if "apple" not in p_brand and "iphone" not in p_name and "apple" not in p_name:
                return {"image_url": "/images/image-unavailable.svg", "image_source": "placeholder", "image_match_level": "unavailable"}

        # Limited Beta Policy: Only display verified_exact_variant or verified_exact_model (or explicitly confirmed verified_product_family)
        if match_level in ["verified_exact_variant", "verified_exact_model"]:
            return {"image_url": img, "image_source": "catalog_cdn", "image_match_level": match_level}
        elif match_level == "verified_product_family":
            if p_brand in ["apple", "samsung", "dell", "hp", "lenovo", "asus", "acer", "google", "oneplus"]:
                return {"image_url": img, "image_source": "catalog_cdn", "image_match_level": "verified_product_family"}
            return {"image_url": "/images/image-unavailable.svg", "image_source": "placeholder", "image_match_level": "unverified"}
        else:
            return {"image_url": "/images/image-unavailable.svg", "image_source": "placeholder", "image_match_level": match_level}

    async def _generate_recommendation_internal(self, decision_id: UUID) -> Recommendation:
        logger.info("Starting upgraded recommendation pipeline", decision_id=str(decision_id))

        # 1. Fetch decision and answers
        decision = await self.decision_repo.get_with_answers(decision_id)
        if not decision:
            raise ValueError(f"Decision session with ID {decision_id} not found.")

        # If the decision is already COMPLETE, return the existing recommendation immediately
        # to avoid redundant calculations, external API calls, and DB write conflicts.
        existing_rec = await self.recommendation_repo.get_by_decision_id(decision_id)
        if decision.status == "COMPLETE" and existing_rec:
            logger.info("Recommendation already exists and decision is COMPLETE. Returning cached result.", decision_id=str(decision_id))
            if existing_rec.verdict_product_id and not existing_rec.verdict_product:
                existing_rec.verdict_product = await self.session.get(Product, existing_rec.verdict_product_id)
            return existing_rec

        target_currency = "inr"
        local_symbol = "₹"

        # Load dynamic merged configuration
        registry = CategoryRegistry()
        if decision.subcategory == "general" or decision.detected_use_case == "general":
            keyword_result = registry.match_keywords(decision.title)
            if keyword_result and keyword_result[0] == decision.category:
                decision.subcategory = keyword_result[1]
                decision.detected_use_case = keyword_result[2]
                logger.info("Dynamically detected subcategory from title", title=decision.title, subcategory=decision.subcategory, persona=decision.detected_use_case)

        config = registry.get(decision.category, decision.subcategory)
        if not config:
            raise ValueError(f"Category configuration for {decision.category} not found.")

        # 2. Gather answers (no conversion needed as base is INR)
        answers_summary = []
        for ans in decision.answers:
            q_text = ans.question.question_text if ans.question else ""
            answers_summary.append({
                "question_id": str(ans.question_id),
                "question_text": q_text,
                "input_type": ans.question.input_type if ans.question else "",
                "selected_value": ans.selected_value,
                "question": ans.question,
                "maps_to": ans.question.weight_impact.get("maps_to") if ans.question and ans.question.weight_impact else None
            })

        # CRITICAL: Commit the transaction now to release SQLite read locks
        # before we make the long-running external Gemini web search API call.
        await self.session.commit()

        # 3. Enrich catalog dynamically using real-time web search
        # DISABLED for Phase X stabilization to ensure deterministic, fast recommendations.
        # try:
        #     from app.services.catalog_enricher import CatalogEnricher
        #     enricher = CatalogEnricher(self.session)
        #     enriched_count = await enricher.enrich_catalog(
        #         query=decision.title, 
        #         category=decision.category, 
        #         currency=target_currency
        #     )
        #     # Commit the catalog enrichment immediately to release the SQLite write lock
        #     await self.session.commit()
        #     logger.info("Catalog enrichment completed successfully", count=enriched_count)
        # except Exception as e:
        #     await self.session.rollback()
        #     logger.error("Catalog enrichment step failed, proceeding with local catalog", error=str(e))

        # 4. Query search providers interface (CatalogProvider)
        provider = LocalCatalogProvider(self.session)
        products = await provider.get_products(decision.category, subtype=decision.subcategory)
        if not products:
            raise ValueError(f"No products found in category: {decision.category}")

        # 4. Run category-agnostic Decision Engine
        engine = DecisionEngine(config)
        scored_results, trace, status = engine.run(
            products, 
            answers_summary, 
            persona_hint=decision.detected_use_case,
            custom_persona_weights=decision.persona_weights,
            intent_confidence=decision.intent_confidence,
            currency_code=target_currency,
            currency_symbol=local_symbol,
            query=decision.title
        )
        
        # Apply active Decision Guardrails
        scored_results, guardrail_log = DecisionGuardrails.evaluate(
            scored_results,
            answers_summary,
            config,
            engine,
            trace,
            local_symbol
        )
        trace["guardrail_results"] = guardrail_log
        
        is_no_match = (status == "no_match_found")
        
        sensitivity_analysis = []
        rel_stability = 100.0
        
        if not is_no_match and scored_results:
            winner = scored_results[0]
            # Parse soft attributes and budget
            soft_attrs = [attr for attr in engine.attributes if not attr.is_hard_filter]
            priorities = {}
            for attr in engine.attributes:
                if not attr.is_hard_filter:
                    priorities[attr.key] = 3.0
            for ans in answers_summary:
                maps_to = ans.get("maps_to")
                val = ans.get("selected_value")
                if isinstance(val, dict):
                    val = val.get("value")
                if maps_to and val is not None:
                    try:
                        val_f = float(val)
                        if maps_to in priorities:
                            priorities[maps_to] = val_f
                    except ValueError:
                        pass
            
            sorted_soft_attrs = sorted(soft_attrs, key=lambda attr: priorities.get(attr.key, 3.0), reverse=True)
            top_soft_attrs = sorted_soft_attrs[:3]
            
            # Parse budget
            budget_inr = None
            for ans in answers_summary:
                maps_to = ans.get("maps_to")
                val = ans.get("selected_value")
                if isinstance(val, dict):
                    val = val.get("value")
                if maps_to == "price" and val is not None:
                    try:
                        budget_inr = float(val)
                    except ValueError:
                        pass
            
            # Lower budget simulation
            if budget_inr is not None:
                sim_answers = []
                for ans in answers_summary:
                    if ans.get("maps_to") == "price":
                        sim_answers.append({**ans, "selected_value": {"value": budget_inr * 0.8}})
                    else:
                        sim_answers.append(ans)
                
                sim_results, _, sim_status = engine.run(
                    products,
                    sim_answers,
                    persona_hint=decision.detected_use_case,
                    custom_persona_weights=decision.persona_weights,
                    intent_confidence=decision.intent_confidence,
                    currency_code=target_currency,
                    currency_symbol=local_symbol,
                    query=decision.title
                )
                if sim_status == "success" and sim_results:
                    sim_winner = sim_results[0].product
                    if sim_winner.sku != winner.product.sku:
                        sensitivity_analysis.append({
                            "parameter": "price",
                            "trigger_condition": f"your budget drops below {local_symbol}{budget_inr * 0.8:,.0f}",
                            "alternative_winner_sku": sim_winner.sku,
                            "alternative_winner_name": sim_winner.name.split(" (")[0].strip()
                        })
            
            # Top soft attributes simulation
            for attr in top_soft_attrs:
                sim_answers = []
                found = False
                for ans in answers_summary:
                    if ans.get("maps_to") == attr.key:
                        sim_answers.append({**ans, "selected_value": {"value": 5.0}})
                        found = True
                    else:
                        sim_answers.append(ans)
                if not found:
                    sim_answers.append({
                        "question_text": f"Importance of {attr.name}",
                        "selected_value": {"value": 5.0},
                        "maps_to": attr.key
                    })
                
                sim_results, _, sim_status = engine.run(
                    products,
                    sim_answers,
                    persona_hint=decision.detected_use_case,
                    custom_persona_weights=decision.persona_weights,
                    intent_confidence=decision.intent_confidence,
                    currency_code=target_currency,
                    currency_symbol=local_symbol,
                    query=decision.title
                )
                if sim_status == "success" and sim_results:
                    sim_winner = sim_results[0].product
                    if sim_winner.sku != winner.product.sku and sim_winner.sku not in [s["alternative_winner_sku"] for s in sensitivity_analysis]:
                        sensitivity_analysis.append({
                            "parameter": attr.key,
                            "trigger_condition": f"{attr.name} becomes a HIGH priority",
                            "alternative_winner_sku": sim_winner.sku,
                            "alternative_winner_name": sim_winner.name.split(" (")[0].strip()
                        })
            
            # Stability simulation for reliability
            sim_answers = []
            if len(top_soft_attrs) >= 2:
                highest_attr = top_soft_attrs[0]
                second_attr = top_soft_attrs[1]
                for ans in answers_summary:
                    if ans.get("maps_to") == highest_attr.key:
                        val = priorities.get(highest_attr.key, 3.0)
                        sim_answers.append({**ans, "selected_value": {"value": max(1.0, val - 0.5)}})
                    elif ans.get("maps_to") == second_attr.key:
                        val = priorities.get(second_attr.key, 3.0)
                        sim_answers.append({**ans, "selected_value": {"value": min(5.0, val + 0.5)}})
                    else:
                        sim_answers.append(ans)
            else:
                sim_answers = answers_summary
            
            sim_results, _, sim_status = engine.run(
                products,
                sim_answers,
                persona_hint=decision.detected_use_case,
                custom_persona_weights=decision.persona_weights,
                intent_confidence=decision.intent_confidence,
                currency_code=target_currency,
                currency_symbol=local_symbol,
                query=decision.title
            )
            if sim_status == "success" and sim_results:
                sim_winner = sim_results[0].product
                if sim_winner.sku != winner.product.sku:
                    rel_stability = 80.0
        
        if is_no_match:
            logger.warning("No products qualified. Activating closest matches fallback.")
            
            # Build explanation using build_no_match
            explanation = ExplanationBuilder.build_no_match(
                closest_matches=trace["closest_matches"],
                trace=trace,
                category_config=config,
                currency_symbol=local_symbol,
                currency_code=target_currency
            )
            
            structured_analysis = {
                "pros": [],
                "cons": [],
                "tradeoffs": [],
                "citations": [],
                "reasoning": explanation["reasoning"],
                "summary": explanation["summary"],
                "local_price": 0.0,
                "local_currency": target_currency,
                "local_symbol": local_symbol,
                "decision_trace": trace,
                "suggestions": explanation["suggestions"],
                "closest_matches": trace["closest_matches"],
                "user_preferences": {
                    "category": decision.category,
                    "subcategory": decision.subcategory,
                    "detected_use_case": decision.detected_use_case,
                    "answers": [
                        {
                            "question_text": ans["question_text"],
                            "selected_value": ans["selected_value"],
                            "maps_to": ans["maps_to"]
                        } for ans in answers_summary
                    ]
                }
            }
            
            # 1. Delete any existing recommendation in the database for this decision
            existing_rec = await self.recommendation_repo.get_by_decision_id(decision_id)
            if existing_rec:
                await self.recommendation_repo.delete(existing_rec.id)
                
            # 2. Update decision status to COMPLETE
            decision.status = "COMPLETE"
            await self.decision_repo.update(decision)
            
            # 3. Construct and return transient Recommendation
            transient_rec = Recommendation(
                decision_id=decision_id,
                verdict_product_id=None,
                confidence_score=0.0,
                structured_analysis=structured_analysis,
                explanation_md=explanation["summary"] + "\n\n" + explanation["reasoning"]
            )
            transient_rec.verdict_product = None
            return transient_rec

        winner = scored_results[0]
        alternatives = scored_results[1:3]

        # Calculate specs tradeoffs compared to winner dynamically
        tradeoffs = DecisionEngine.calculate_tradeoffs(
            winner, 
            alternatives, 
            tradeoff_config=config.tradeoff_comparisons,
            currency_code=target_currency,
            currency_symbol=local_symbol
        )

        # Enrich tradeoffs with full product details for the frontend modal
        for idx, alt in enumerate(alternatives):
            if idx < len(tradeoffs):
                tradeoffs[idx]["alternative_specs"] = alt.product.specs
                tradeoffs[idx]["alternative_price"] = float(alt.product.price_inr)
                tradeoffs[idx]["alternative_configurations"] = alt.configurations
                
        # Attach configurations to the winner product so the Pydantic schema picks it up
        setattr(winner.product, "configurations", winner.configurations)

        # 5. Build Structured Recommendation using ExplanationBuilder
        explanation = ExplanationBuilder.build(
            winner=winner,
            alternatives=alternatives,
            tradeoffs=tradeoffs,
            trace=trace,
            category_config=config,
            currency_symbol=local_symbol,
            currency_code=target_currency
        )

        # Structure the final explanation analysis
        winner_local_price = float(winner.product.price_inr)
        
        # Build recommendation debug mode info
        details = trace["pipeline_trace"][4].get("details", {})
        debug_trace = {
            "loaded_products": len(products),
            "subtype_products": details.get("Subtype", 0),
            "budget_passed": details.get("Budget", 0),
            "hard_constraints_passed": details.get("Stock", 0),
            "mcda_candidates": details.get("Stock", 0),
            "winner": winner.product.name,
            "winner_score": round(winner.score * 100, 1),
            "runner_up": alternatives[0].product.name if len(alternatives) > 0 else None,
            "runner_up_score": round(alternatives[0].score * 100, 1) if len(alternatives) > 0 else None,
            "reason": explanation.get("pros", [])[:2] + explanation.get("cons", [])[:1],
            "winner_scoring_breakdown": winner.scoring_breakdown,
            "alternatives_scoring_breakdown": [a.scoring_breakdown for a in alternatives]
        }
        trace["debug_trace"] = debug_trace

        # Calculate use case ranking & domain scores
        from app.services.score_calculator import ScoreCalculator
        winner_domain_scores = ScoreCalculator.calculate_all(decision.category, winner.product.specs, float(winner.product.price_inr))
        winner_domain_scores = {k.replace("_score", ""): round(v * 10, 1) for k, v in winner_domain_scores.items()}

        # Extract CPU and GPU values for percentiles
        all_cpus = []
        all_gpus = []
        for p in products:
            cpu_val = p.specs.get("cpu_score") or p.specs.get("cpu_multi_core") or p.specs.get("processor_score")
            gpu_val = p.specs.get("gpu_score") or p.specs.get("gpu_score_3dmark")
            if cpu_val is not None:
                try:
                    all_cpus.append(float(cpu_val))
                except (ValueError, TypeError):
                    pass
            if gpu_val is not None:
                try:
                    all_gpus.append(float(gpu_val))
                except (ValueError, TypeError):
                    pass

        w_cpu = winner.product.specs.get("cpu_score") or winner.product.specs.get("cpu_multi_core") or winner.product.specs.get("processor_score")
        w_gpu = winner.product.specs.get("gpu_score") or winner.product.specs.get("gpu_score_3dmark")

        def calculate_percentile(target_val, all_vals):
            if not all_vals or target_val is None:
                return 50.0
            try:
                target_float = float(target_val)
            except (ValueError, TypeError):
                return 50.0
            sorted_vals = sorted(all_vals)
            smaller = sum(1 for v in sorted_vals if v <= target_float)
            return round((smaller / len(sorted_vals)) * 100, 1)

        cpu_percentile = calculate_percentile(w_cpu, all_cpus) if w_cpu is not None else None
        gpu_percentile = calculate_percentile(w_gpu, all_gpus) if w_gpu is not None else None

        use_case = decision.subcategory.lower() if decision.subcategory else "gaming"
        score_key_map = {
            "gaming": "gaming_score",
            "developer": "programming_score",
            "programming": "programming_score",
            "creator": "creator_score",
            "business": "business_score",
            "student": "student_score",
            "general": "business_score"
        }
        target_score_key = score_key_map.get(use_case, "gaming_score")
        
        scored_pool = []
        for p in products:
            scores = ScoreCalculator.calculate_all(decision.category, p.specs, float(p.price_inr))
            scored_pool.append((p.sku, scores.get(target_score_key, 0.0)))
        
        scored_pool.sort(key=lambda x: -x[1])
        winner_rank = 1
        for idx, (sku, score) in enumerate(scored_pool):
            if sku == winner.product.sku:
                winner_rank = idx + 1
                break

        # Build Funnel Metrics
        pipeline = trace.get("pipeline_trace", [])
        total_compared = pipeline[3].get("count", 0) if len(pipeline) > 3 else len(products)
        
        funnel_metrics = {
            "total_compared": total_compared,
            "category_matched": details.get("Subtype", total_compared),
            "budget_passed": details.get("Budget", 0),
            "constraints_passed": details.get("Stock", 0),
            "ranked": len(trace.get("ranking", []))
        }
        
        # Build Cheaper Alternative Spend Less Analysis
        spend_less_analysis = None
        cheaper_alt = None
        best_savings_efficiency = -1.0
        
        winner_price = float(winner.product.price_inr)
        winner_score = float(winner.score)
        
        for cand in scored_results[1:]:
            cand_price = float(cand.product.price_inr)
            cand_score = float(cand.score)
            
            if cand_price < winner_price:
                pct_savings = ((winner_price - cand_price) / winner_price) * 100.0
                retained_utility = (cand_score / winner_score) * 100.0
                
                # Minimum savings 5% and minimum utility 85%
                if pct_savings >= 5.0 and retained_utility >= 85.0:
                    suitability_loss = (winner_score - cand_score) * 100.0
                    savings_efficiency = pct_savings / (suitability_loss + 1.0)
                    
                    if savings_efficiency > best_savings_efficiency:
                        best_savings_efficiency = savings_efficiency
                        cheaper_alt = cand
                        
        if cheaper_alt:
            alt_price = float(cheaper_alt.product.price_inr)
            price_savings = winner_price - alt_price
            pct_savings = (price_savings / winner_price) * 100.0
            retained_utility = (float(cheaper_alt.score) / winner_score) * 100.0
            suitability_diff = (winner_score - float(cheaper_alt.score)) * 100.0
            
            # Categorize verdict
            if retained_utility >= 95.0 and pct_savings >= 15.0:
                spend_less_verdict = "Strong cheaper alternative"
            elif retained_utility >= 90.0:
                spend_less_verdict = "Worth considering"
            elif retained_utility >= 85.0:
                spend_less_verdict = "Meaningful compromises"
            else:
                spend_less_verdict = "Stick with the winner"
                
            # Generic loss and similarities logic
            spec_losses = []
            spec_similarities = []
            
            for attr in config.attributes:
                if attr.key == "price":
                    continue
                w_val = engine._get_spec_val(winner.product, attr.key)
                c_val = engine._get_spec_val(cheaper_alt.product, attr.key)
                
                if w_val is not None and c_val is not None:
                    if attr.type == "benefit":
                        if c_val < w_val:
                            pct_loss = round(((w_val - c_val) / w_val) * 100.0) if w_val > 0 else 0
                            spec_losses.append(f"{pct_loss}% lower {attr.name}")
                        else:
                            spec_similarities.append(f"Similar {attr.name}")
                    else:  # cost (e.g. weight_kg: lower is better)
                        if c_val > w_val:
                            pct_loss = round(((c_val - w_val) / w_val) * 100.0) if w_val > 0 else 0
                            spec_losses.append(f"{pct_loss}% higher {attr.name}")
                        else:
                            spec_similarities.append(f"Similar {attr.name}")
                            
            if not spec_losses:
                spec_losses.append("Slightly lower overall specifications")
            if not spec_similarities:
                spec_similarities.append("Core functionality")
                
            spend_less_analysis = {
                "status": "spend_less_available",
                "sku": cheaper_alt.product.sku,
                "name": cheaper_alt.product.name.split(" (")[0].strip(),
                "price": alt_price,
                "price_savings": price_savings,
                "percentage_savings": pct_savings,
                "suitability_difference": suitability_diff,
                "retained_utility_percentage": retained_utility,
                "savings_efficiency": best_savings_efficiency,
                "important_spec_losses": spec_losses,
                "important_spec_similarities": spec_similarities,
                "verdict": spend_less_verdict
            }
        else:
            spend_less_analysis = {
                "status": "no_cheaper_option_found",
                "sku": None,
                "name": "No lower-priced alternative found",
                "price": 0.0,
                "price_savings": 0.0,
                "percentage_savings": 0.0,
                "verdict": "Winner is already the best value candidate within this price tier"
            }

        # Build Upgrade / Worth Upgrading Analysis (Category-Agnostic across Laptop, Smartphone, Monitor)
        upgrade_analysis = None
        more_expensive = [cand for cand in scored_results if float(cand.product.price_inr) > winner_local_price]
        if not more_expensive and len(products) > 0:
            max_budget_limit = winner_local_price * 1.35
            higher_prods = [p for p in products if float(p.price_inr) > winner_local_price and float(p.price_inr) <= max_budget_limit * 1.35]
            if higher_prods:
                scored_higher, _, _ = engine.run(higher_prods[:15], answers_summary, currency_symbol=local_symbol)
                more_expensive = sorted([sc for sc in scored_higher if sc], key=lambda x: float(x.product.price_inr))

        if more_expensive:
            target_up = min(more_expensive, key=lambda x: float(x.product.price_inr))
            up_price = float(target_up.product.price_inr)
            price_diff = up_price - winner_local_price

            absolute_utility_gain = float(target_up.score) - winner_score
            percentage_utility_gain = absolute_utility_gain * 100.0
            utility_gain_per_10k = percentage_utility_gain / (price_diff / 10000.0) if price_diff > 0 else 0.0

            if percentage_utility_gain >= 8.0 and utility_gain_per_10k >= 4.0:
                rec_verdict = "Highly recommended upgrade"
                up_status = "upgrade_recommended"
            elif percentage_utility_gain >= 2.0 and utility_gain_per_10k >= 1.5:
                rec_verdict = "Worth considering upgrade"
                up_status = "upgrade_recommended"
            else:
                rec_verdict = "Not worth upgrading"
                up_status = "not_worth_upgrading"

            up_gains = []
            for attr in config.attributes:
                if attr.key == "price":
                    continue
                w_val = engine._get_spec_val(winner.product, attr.key)
                u_val = engine._get_spec_val(target_up.product, attr.key)
                if w_val is not None and u_val is not None:
                    if attr.type == "benefit" and u_val > w_val:
                        up_gains.append(f"Better {attr.name} ({u_val} vs {w_val})")
                    elif attr.type == "cost" and u_val < w_val:
                        up_gains.append(f"Better {attr.name} ({u_val} vs {w_val})")

            if not up_gains:
                up_gains.append("Slightly higher overall specifications")

            upgrade_analysis = {
                "status": up_status,
                "sku": target_up.product.sku,
                "name": target_up.product.name.split(" (")[0].strip(),
                "price": up_price,
                "extra_cost": price_diff,
                "absolute_utility_gain": absolute_utility_gain,
                "percentage_utility_gain": percentage_utility_gain,
                "utility_gain_per_10k": utility_gain_per_10k,
                "gains": up_gains,
                "verdict": rec_verdict,
                "image_provenance": RecommendationService._determine_image_provenance(target_up.product)
            }
        else:
            upgrade_analysis = {
                "status": "no_upgrade_available",
                "sku": None,
                "name": "No higher-tier upgrade candidate found",
                "price": 0.0,
                "extra_cost": 0.0,
                "absolute_utility_gain": 0.0,
                "percentage_utility_gain": 0.0,
                "utility_gain_per_10k": 0.0,
                "gains": [],
                "verdict": "No suitable upgrade candidate found within a reasonable price range",
                "image_provenance": RecommendationService._determine_image_provenance(None)
            }
                
        # Build Runner-Up Battle Comparison
        battle_comparison = None
        if len(scored_results) >= 2:
            runner = scored_results[1]
            w_specs = winner.product.specs
            r_specs = runner.product.specs
            
            deltas = []
            
            w_price = float(winner.product.price_inr)
            r_price = float(runner.product.price_inr)
            if w_price < r_price:
                diff = r_price - w_price
                deltas.append({
                    "label": "Price",
                    "winner_val": f"₹{w_price:,.0f}",
                    "runner_val": f"₹{r_price:,.0f}",
                    "delta_text": f"₹{diff:,.0f} cheaper",
                    "status": "better"
                })
            elif w_price > r_price:
                diff = w_price - r_price
                deltas.append({
                    "label": "Price",
                    "winner_val": f"₹{w_price:,.0f}",
                    "runner_val": f"₹{r_price:,.0f}",
                    "delta_text": f"₹{diff:,.0f} more expensive",
                    "status": "worse"
                })
                
            def get_percent_delta(w_val, r_val):
                try:
                    wv = float(w_val)
                    rv = float(r_val)
                    if rv == 0: return 0.0
                    return round(((wv - rv) / rv) * 100.0, 1)
                except (ValueError, TypeError):
                    return 0.0
                    
            w_cpu = w_specs.get("cpu_score") or w_specs.get("cpu_multi_core") or w_specs.get("processor_score")
            r_cpu = r_specs.get("cpu_score") or r_specs.get("cpu_multi_core") or r_specs.get("processor_score")
            if w_cpu and r_cpu:
                pct = get_percent_delta(w_cpu, r_cpu)
                if pct > 0:
                    deltas.append({
                        "label": "CPU Performance",
                        "winner_val": str(w_cpu),
                        "runner_val": str(r_cpu),
                        "delta_text": f"{pct}% faster CPU",
                        "status": "better"
                    })
                elif pct < 0:
                    deltas.append({
                        "label": "CPU Performance",
                        "winner_val": str(w_cpu),
                        "runner_val": str(r_cpu),
                        "delta_text": f"{abs(pct)}% slower CPU",
                        "status": "worse"
                    })
                    
            w_gpu = w_specs.get("gpu_score") or w_specs.get("gpu_score_3dmark")
            r_gpu = r_specs.get("gpu_score") or r_specs.get("gpu_score_3dmark")
            if w_gpu and r_gpu:
                pct = get_percent_delta(w_gpu, r_gpu)
                if pct > 0:
                    deltas.append({
                        "label": "GPU Capability",
                        "winner_val": str(w_gpu),
                        "runner_val": str(r_gpu),
                        "delta_text": f"{pct}% faster GPU",
                        "status": "better"
                    })
                elif pct < 0:
                    deltas.append({
                        "label": "GPU Capability",
                        "winner_val": str(w_gpu),
                        "runner_val": str(r_gpu),
                        "delta_text": f"{abs(pct)}% slower GPU",
                        "status": "worse"
                    })
                    
            w_bat = w_specs.get("battery_hours") or w_specs.get("estimated_office_hours")
            r_bat = r_specs.get("battery_hours") or r_specs.get("estimated_office_hours")
            if w_bat and r_bat:
                try:
                    diff = float(w_bat) - float(r_bat)
                    if diff > 0:
                        deltas.append({
                            "label": "Battery Life",
                            "winner_val": f"{w_bat} hrs",
                            "runner_val": f"{r_bat} hrs",
                            "delta_text": f"{round(diff, 1)} hours more battery",
                            "status": "better"
                        })
                    elif diff < 0:
                        deltas.append({
                            "label": "Battery Life",
                            "winner_val": f"{w_bat} hrs",
                            "runner_val": f"{r_bat} hrs",
                            "delta_text": f"{round(abs(diff), 1)} hours less battery",
                            "status": "worse"
                        })
                except (ValueError, TypeError):
                    pass
                    
            battle_comparison = {
                "runner_name": runner.product.name.split(" (")[0].strip(),
                "runner_sku": runner.product.sku,
                "winner_score": round(winner.score * 100, 1),
                "runner_score": round(runner.score * 100, 1),
                "deltas": deltas
            }

        # Calculate Reliability Score & detailed breakdown
        matched_cnt = funnel_metrics["constraints_passed"]
        rel_intent = float(decision.intent_confidence or 95.0)
        
        filled_specs = len([k for k, v in winner.product.specs.items() if v is not None])
        total_config_specs = max(1, len(config.attributes))
        rel_spec = min(100.0, (filled_specs / total_config_specs) * 100.0)
        
        rel_catalog = min(100.0, 50.0 + min(50.0, matched_cnt * 2.0))
        
        if len(scored_results) >= 2:
            margin = winner.score - scored_results[1].score
            rel_margin = min(100.0, 70.0 + margin * 300.0)
        else:
            rel_margin = 100.0
            
        present_attrs = sum(1 for attr in config.attributes if engine._get_spec_val(winner.product, attr.key) is not None)
        rel_completeness = (present_attrs / len(config.attributes)) * 100.0 if config.attributes else 100.0
        
        # Stability check
        rel_stability_score = float(rel_stability)
        
        reliability_score = round(0.20 * rel_intent + 0.15 * rel_spec + 0.15 * rel_catalog + 0.20 * rel_margin + 0.15 * rel_completeness + 0.15 * rel_stability_score, 1)
        
        reliability_reasons = []
        if rel_intent >= 90:
            reliability_reasons.append("Intent clearly understood")
        else:
            reliability_reasons.append("Ambiguous intent fallback")
            
        if rel_spec >= 80:
            reliability_reasons.append("Complete specifications coverage")
        else:
            reliability_reasons.append("Partial specifications coverage")
            
        reliability_reasons.append(f"{matched_cnt} eligible candidates analyzed")
        
        if len(scored_results) >= 2:
            margin = winner.score - scored_results[1].score
            if margin >= 0.08:
                reliability_reasons.append("Clear advantage over runner-up")
            elif margin >= 0.03:
                reliability_reasons.append("Moderate advantage over runner-up")
            else:
                reliability_reasons.append("Narrow margin over runner-up")
        else:
            reliability_reasons.append("No other candidates found")
            
        if rel_stability_score == 100.0:
            reliability_reasons.append("Recommendation is stable under priority changes")
        else:
            reliability_reasons.append("Recommendation changes under priority variations")
            
        reliability_breakdown = {
            "intent_confidence": rel_intent,
            "specification_coverage": rel_spec,
            "catalog_coverage": rel_catalog,
            "score_margin": rel_margin,
            "data_completeness": rel_completeness,
            "stability_score": rel_stability_score
        }

        # Build Detailed Confidence Breakdown
        win_margin = 90.0
        if len(alternatives) > 0:
            win_margin = min(100.0, max(50.0, 70.0 + (winner.score - alternatives[0].score) * 100.0))
            
        confidence_breakdown = {
            "category_detection": 100.0,
            "budget_match": 100.0,
            "spec_match": round(min(100.0, winner.score * 100 + 10), 1),
            "winner_margin": round(win_margin, 1),
            "catalog_coverage": 93.0
        }

        structured_analysis = {
            "pros": explanation["pros"],
            "cons": explanation["cons"],
            "tradeoffs": tradeoffs,
            "reasoning": explanation["reasoning"],
            "summary": explanation["summary"],
            "citations": explanation["citations"],
            "local_price": winner_local_price,
            "local_currency": target_currency,
            "local_symbol": local_symbol,
            "funnel_metrics": funnel_metrics,
            "confidence_breakdown": confidence_breakdown,
            "decision_trace": trace,
            "debug_trace": debug_trace,
            "domain_scores": winner_domain_scores,
            "component_percentiles": {
                "cpu": cpu_percentile,
                "gpu": gpu_percentile
            },
            "use_case_rank": {
                "rank": winner_rank,
                "total": len(products),
                "name": use_case.capitalize()
            },
            "reliability_score": reliability_score,
            "reliability_reasons": reliability_reasons,
            "battle_comparison": battle_comparison,
            "upgrade_analysis": upgrade_analysis,
            "spend_less_analysis": spend_less_analysis,
            "sensitivity_analysis": sensitivity_analysis,
            "reliability_breakdown": reliability_breakdown,
            "user_preferences": {
                "category": decision.category,
                "subcategory": decision.subcategory,
                "detected_use_case": decision.detected_use_case,
                "answers": [
                    {
                        "question_text": ans["question_text"],
                        "selected_value": ans["selected_value"],
                        "maps_to": ans["maps_to"]
                    } for ans in answers_summary
                ]
            }
        }

        # Run read-only Decision Invariant Auditor
        payload_for_audit = {
            "verdict_product": {
                "id": str(winner.product.id),
                "sku": winner.product.sku,
                "name": winner.product.name,
                "price": float(winner.product.price_inr),
                "specs": winner.product.specs
            },
            "score": float(winner.score),
            "confidence": float(winner.confidence_score)
        }
        audit_status, audit_violations = DecisionInvariantAuditor.audit(
            payload_for_audit,
            structured_analysis,
            engine,
            config
        )
        structured_analysis["decision_trace"]["audit_status"] = audit_status
        structured_analysis["decision_trace"]["audit_violations"] = audit_violations

        # 2-Tier audit tracing (full_audit_trace for dev/debug only)
        full_audit_trace = {
            "raw_scores": [
                {
                    "sku": cand.product.sku,
                    "name": cand.product.name,
                    "score": float(cand.score),
                    "normalized_values": getattr(cand, 'normalized_values', {}),
                    "raw_values": getattr(cand, 'raw_values', {}),
                    "scoring_breakdown": getattr(cand, 'scoring_breakdown', {})
                } for cand in scored_results
            ],
            "pareto_evidence": trace.get("pareto_analysis", {}).get("dominated_products", []),
            "explanation_evidence": explanation.get("evidence", []),
            "guardrail_log": trace.get("guardrail_results", {})
        }
        structured_analysis["full_audit_trace"] = full_audit_trace

        # 6. Commit to database
        from sqlalchemy.exc import IntegrityError
        try:
            # Use a savepoint (nested transaction) to handle concurrent insert conflicts gracefully
            async with self.session.begin_nested():
                existing_rec = await self.recommendation_repo.get_by_decision_id(decision_id)
                
                if existing_rec:
                    existing_rec.verdict_product_id = winner.product.id
                    existing_rec.confidence_score = winner.confidence_score
                    existing_rec.structured_analysis = structured_analysis
                    existing_rec.explanation_md = explanation["summary"] + "\n\n" + explanation["reasoning"]
                    
                    next_version = len(existing_rec.versions) + 1
                    version_log = RecommendationVersion(
                        recommendation_id=existing_rec.id,
                        version_index=next_version,
                        trigger_reason="pipeline_calculation",
                        verdict_product_id=winner.product.id,
                        confidence_score=winner.confidence_score,
                        delta_analysis={"tradeoffs": tradeoffs, "status": status}
                    )
                    existing_rec.versions.append(version_log)
                    
                    await self.recommendation_repo.update(existing_rec)
                    rec_result = existing_rec
                else:
                    new_rec = Recommendation(
                        decision_id=decision_id,
                        verdict_product_id=winner.product.id,
                        confidence_score=winner.confidence_score,
                        structured_analysis=structured_analysis,
                        explanation_md=explanation["summary"] + "\n\n" + explanation["reasoning"]
                    )
                    
                    version_log = RecommendationVersion(
                        version_index=1,
                        trigger_reason="initial_recommendation",
                        verdict_product_id=winner.product.id,
                        confidence_score=winner.confidence_score,
                        delta_analysis={"tradeoffs": tradeoffs, "status": status}
                    )
                    new_rec.versions.append(version_log)
                    
                    rec_result = await self.recommendation_repo.create(new_rec)

                # Update decision status
                decision.status = "COMPLETE"
                await self.decision_repo.update(decision)
                
            return rec_result

        except IntegrityError as ie:
            logger.warn("IntegrityError during recommendation save, likely concurrent requests. Recovering via savepoint...", error=str(ie))
            # The nested transaction is automatically rolled back. The main session is still clean and active.
            # Fetch the recommendation created by the concurrent request
            existing_rec = await self.recommendation_repo.get_by_decision_id(decision_id)
            if existing_rec:
                # Update decision status in the main session
                decision.status = "COMPLETE"
                await self.decision_repo.update(decision)
                existing_rec.verdict_product = winner.product
                logger.info("Successfully recovered recommendation from concurrent request via savepoint")
                return existing_rec
            raise

    async def generate_recommendation_stateless(self, payload) -> Dict[str, Any]:
        """
        Runs the recommendation pipeline statelessly.
        """
        if isinstance(payload, dict):
            category = str(payload.get("category", "laptop")).lower()
            subcategory = str(payload.get("subcategory", "general")).lower()
            persona = str(payload.get("persona", "general")).lower()
            target_currency = str(payload.get("currency", "inr")).lower()
            raw_answers = payload.get("answers", [])
        else:
            category = payload.category.lower()
            subcategory = payload.subcategory.lower()
            persona = payload.persona.lower()
            target_currency = payload.currency.lower()
            raw_answers = payload.answers

        local_symbol = "₹" if target_currency == "inr" else "$"

        # Load dynamic merged configuration
        registry = CategoryRegistry()
        config = registry.get(category, subcategory)
        if not config:
            raise ValueError(f"Category configuration for {category} not found.")

        # Match questions with answers to build answers_summary
        answers_summary = []
        for ans in raw_answers:
            if isinstance(ans, dict):
                q_id = ans.get("question_id") or ans.get("maps_to")
                sel_val = ans.get("selected_value")
                maps_to_key = ans.get("maps_to")
            else:
                q_id = ans.question_id
                sel_val = ans.selected_value
                maps_to_key = getattr(ans, "maps_to", None)

            # Find matching question in config
            q_cfg = None
            for q in config.questions:
                if q.order_index == q_id or q.maps_to == q_id or q.maps_to == maps_to_key:
                    q_cfg = q
                    break
            
            if q_cfg:
                answers_summary.append({
                    "question_id": str(q_cfg.order_index),
                    "question_text": q_cfg.question_text,
                    "input_type": q_cfg.input_type,
                    "selected_value": sel_val,
                    "question": {
                        "question_text": q_cfg.question_text,
                        "input_type": q_cfg.input_type,
                        "weight_impact": {"maps_to": q_cfg.maps_to}
                    },
                    "maps_to": q_cfg.maps_to
                })
            elif maps_to_key:
                answers_summary.append({
                    "question_id": str(q_id or "1"),
                    "question_text": str(maps_to_key),
                    "input_type": "budget_range" if maps_to_key == "price" else "single_choice",
                    "selected_value": sel_val,
                    "maps_to": maps_to_key
                })

        # Query products from catalog provider
        provider = LocalCatalogProvider(self.session)
        products = await provider.get_products(category, subtype=subcategory)
        if not products:
            raise ValueError(f"No products found in category: {category}")

        # Run category-agnostic Decision Engine
        engine = DecisionEngine(config)
        scored_results, trace, status = engine.run(
            products, 
            answers_summary, 
            persona_hint=persona,
            custom_persona_weights=None,
            intent_confidence=100.0,
            currency_code=target_currency,
            currency_symbol=local_symbol,
            query=""
        )
        
        # Apply active Decision Guardrails
        scored_results, guardrail_log = DecisionGuardrails.evaluate(
            scored_results,
            answers_summary,
            config,
            engine,
            trace,
            local_symbol
        )
        trace["guardrail_results"] = guardrail_log
        
        is_no_match = (status == "no_match_found")
        
        if is_no_match:
            logger.warning("No products qualified. Activating closest matches fallback.")
            explanation = ExplanationBuilder.build_no_match(
                closest_matches=trace["closest_matches"],
                trace=trace,
                category_config=config,
                currency_symbol=local_symbol,
                currency_code=target_currency
            )
            
            structured_analysis = {
                "pros": [],
                "cons": [],
                "tradeoffs": [],
                "citations": [],
                "reasoning": explanation["reasoning"],
                "summary": explanation["summary"],
                "local_price": 0.0,
                "local_currency": target_currency,
                "local_symbol": local_symbol,
                "decision_trace": trace,
                "suggestions": explanation["suggestions"],
                "closest_matches": trace["closest_matches"]
            }
            
            return {
                "id": None,
                "decision_id": None,
                "verdict_product_id": None,
                "verdict_product": None,
                "confidence_score": 0.0,
                "structured_analysis": structured_analysis,
                "explanation_md": explanation["summary"] + "\n\n" + explanation["reasoning"]
            }

        winner = scored_results[0]
        alternatives = scored_results[1:3]

        # Calculate specs tradeoffs compared to winner dynamically
        tradeoffs = DecisionEngine.calculate_tradeoffs(
            winner, 
            alternatives, 
            tradeoff_config=config.tradeoff_comparisons,
            currency_code=target_currency,
            currency_symbol=local_symbol
        )

        # Enrich tradeoffs with info for frontend
        for idx, alt in enumerate(alternatives):
            if idx < len(tradeoffs):
                tradeoffs[idx]["alternative_specs"] = alt.product.specs
                tradeoffs[idx]["alternative_price"] = float(alt.product.price_inr)

        # Build Structured Recommendation using ExplanationBuilder
        explanation = ExplanationBuilder.build(
            winner=winner,
            alternatives=alternatives,
            tradeoffs=tradeoffs,
            trace=trace,
            category_config=config,
            currency_symbol=local_symbol,
            currency_code=target_currency
        )

        winner_local_price = float(winner.product.price_inr)
        winner_score = float(winner.score)
        
        # Build Cheaper Alternative Spend Less Analysis
        spend_less_analysis = None
        cheaper_alt = None
        best_savings_efficiency = -1.0
        
        for cand in scored_results[1:]:
            cand_price = float(cand.product.price_inr)
            cand_score = float(cand.score)
            
            if cand_price < winner_local_price:
                pct_savings = ((winner_local_price - cand_price) / winner_local_price) * 100.0
                retained_utility = (cand_score / winner_score) * 100.0
                
                # Minimum savings 5% and minimum utility 85%
                if pct_savings >= 5.0 and retained_utility >= 85.0:
                    suitability_loss = (winner_score - cand_score) * 100.0
                    savings_efficiency = pct_savings / (suitability_loss + 1.0)
                    
                    if savings_efficiency > best_savings_efficiency:
                        best_savings_efficiency = savings_efficiency
                        cheaper_alt = cand
                        
        if cheaper_alt:
            alt_price = float(cheaper_alt.product.price_inr)
            price_savings = winner_local_price - alt_price
            pct_savings = (price_savings / winner_local_price) * 100.0
            retained_utility = (float(cheaper_alt.score) / winner_score) * 100.0
            suitability_diff = (winner_score - float(cheaper_alt.score)) * 100.0
            
            # Categorize verdict
            if retained_utility >= 95.0 and pct_savings >= 15.0:
                spend_less_verdict = "Strong cheaper alternative"
            elif retained_utility >= 90.0:
                spend_less_verdict = "Worth considering"
            elif retained_utility >= 85.0:
                spend_less_verdict = "Meaningful compromises"
            else:
                spend_less_verdict = "Stick with the winner"
                
            spec_losses = []
            spec_similarities = []
            
            for attr in config.attributes:
                if attr.key == "price":
                    continue
                w_val = engine._get_spec_val(winner.product, attr.key)
                c_val = engine._get_spec_val(cheaper_alt.product, attr.key)
                
                if w_val is not None and c_val is not None:
                    if attr.type == "benefit":
                        if c_val < w_val:
                            pct_loss = round(((w_val - c_val) / w_val) * 100.0) if w_val > 0 else 0
                            spec_losses.append(f"{pct_loss}% lower {attr.name}")
                        else:
                            spec_similarities.append(f"Similar {attr.name}")
                    else:  # cost
                        if c_val > w_val:
                            pct_loss = round(((c_val - w_val) / w_val) * 100.0) if w_val > 0 else 0
                            spec_losses.append(f"{pct_loss}% higher {attr.name}")
                        else:
                            spec_similarities.append(f"Similar {attr.name}")
                            
            if not spec_losses:
                spec_losses.append("Slightly lower overall specifications")
            if not spec_similarities:
                spec_similarities.append("Core functionality")
                
            spend_less_analysis = {
                "status": "spend_less_available",
                "sku": cheaper_alt.product.sku,
                "name": cheaper_alt.product.name.split(" (")[0].strip(),
                "price": alt_price,
                "price_savings": price_savings,
                "percentage_savings": pct_savings,
                "suitability_difference": suitability_diff,
                "retained_utility_percentage": retained_utility,
                "savings_efficiency": best_savings_efficiency,
                "important_spec_losses": spec_losses,
                "important_spec_similarities": spec_similarities,
                "verdict": spend_less_verdict
            }
        else:
            spend_less_analysis = {
                "status": "no_cheaper_option_found",
                "sku": None,
                "name": "No lower-priced alternative found",
                "price": 0.0,
                "price_savings": 0.0,
                "percentage_savings": 0.0,
                "verdict": "Winner is already the best value candidate within this price tier"
            }

        # Build Upgrade / Worth Upgrading Analysis (Category-Agnostic across Laptop, Smartphone, Monitor)
        upgrade_analysis = None
        more_expensive = [cand for cand in scored_results if float(cand.product.price_inr) > winner_local_price]
        if not more_expensive and len(products) > 0:
            max_budget_limit = winner_local_price * 1.35
            higher_prods = [p for p in products if float(p.price_inr) > winner_local_price and float(p.price_inr) <= max_budget_limit * 1.35]
            if higher_prods:
                scored_higher, _, _ = engine.run(higher_prods[:15], answers_summary, currency_symbol=local_symbol)
                more_expensive = sorted([sc for sc in scored_higher if sc], key=lambda x: float(x.product.price_inr))

        if more_expensive:
            target_up = min(more_expensive, key=lambda x: float(x.product.price_inr))
            up_price = float(target_up.product.price_inr)
            price_diff = up_price - winner_local_price

            absolute_utility_gain = float(target_up.score) - winner_score
            percentage_utility_gain = absolute_utility_gain * 100.0
            utility_gain_per_10k = percentage_utility_gain / (price_diff / 10000.0) if price_diff > 0 else 0.0

            if percentage_utility_gain >= 8.0 and utility_gain_per_10k >= 4.0:
                rec_verdict = "Highly recommended upgrade"
                up_status = "upgrade_recommended"
            elif percentage_utility_gain >= 2.0 and utility_gain_per_10k >= 1.5:
                rec_verdict = "Worth considering upgrade"
                up_status = "upgrade_recommended"
            else:
                rec_verdict = "Not worth upgrading"
                up_status = "not_worth_upgrading"

            up_gains = []
            for attr in config.attributes:
                if attr.key == "price":
                    continue
                w_val = engine._get_spec_val(winner.product, attr.key)
                u_val = engine._get_spec_val(target_up.product, attr.key)
                if w_val is not None and u_val is not None:
                    if attr.type == "benefit" and u_val > w_val:
                        up_gains.append(f"Better {attr.name} ({u_val} vs {w_val})")
                    elif attr.type == "cost" and u_val < w_val:
                        up_gains.append(f"Better {attr.name} ({u_val} vs {w_val})")

            if not up_gains:
                up_gains.append("Slightly higher overall specifications")

            upgrade_analysis = {
                "status": up_status,
                "sku": target_up.product.sku,
                "name": target_up.product.name.split(" (")[0].strip(),
                "price": up_price,
                "extra_cost": price_diff,
                "absolute_utility_gain": absolute_utility_gain,
                "percentage_utility_gain": percentage_utility_gain,
                "utility_gain_per_10k": utility_gain_per_10k,
                "gains": up_gains,
                "verdict": rec_verdict,
                "image_provenance": RecommendationService._determine_image_provenance(target_up.product)
            }
        else:
            upgrade_analysis = {
                "status": "no_upgrade_available",
                "sku": None,
                "name": "No higher-tier upgrade candidate found",
                "price": 0.0,
                "extra_cost": 0.0,
                "absolute_utility_gain": 0.0,
                "percentage_utility_gain": 0.0,
                "utility_gain_per_10k": 0.0,
                "gains": [],
                "verdict": "No suitable upgrade candidate found within a reasonable price range",
                "image_provenance": RecommendationService._determine_image_provenance(None)
            }

        # Build Runner-Up Battle Comparison
        battle_comparison = None
        if len(scored_results) >= 2:
            runner = scored_results[1]
            w_specs = winner.product.specs
            r_specs = runner.product.specs
            
            deltas = []
            
            w_price = float(winner.product.price_inr)
            r_price = float(runner.product.price_inr)
            if w_price < r_price:
                diff = r_price - w_price
                deltas.append({
                    "label": "Price",
                    "winner_val": f"₹{w_price:,.0f}",
                    "runner_val": f"₹{r_price:,.0f}",
                    "delta_text": f"₹{diff:,.0f} cheaper",
                    "status": "better"
                })
            elif w_price > r_price:
                diff = w_price - r_price
                deltas.append({
                    "label": "Price",
                    "winner_val": f"₹{w_price:,.0f}",
                    "runner_val": f"₹{r_price:,.0f}",
                    "delta_text": f"₹{diff:,.0f} more expensive",
                    "status": "worse"
                })
                
            def get_percent_delta(w_val, r_val):
                try:
                    wv = float(w_val)
                    rv = float(r_val)
                    if rv == 0: return 0.0
                    return round(((wv - rv) / rv) * 100.0, 1)
                except (ValueError, TypeError):
                    return 0.0
                    
            w_cpu = w_specs.get("cpu_score") or w_specs.get("cpu_multi_core") or w_specs.get("processor_score")
            r_cpu = r_specs.get("cpu_score") or r_specs.get("cpu_multi_core") or r_specs.get("processor_score")
            if w_cpu and r_cpu:
                pct = get_percent_delta(w_cpu, r_cpu)
                if pct > 0:
                    deltas.append({
                        "label": "CPU Performance",
                        "winner_val": str(w_cpu),
                        "runner_val": str(r_cpu),
                        "delta_text": f"{pct}% faster CPU",
                        "status": "better"
                    })
                elif pct < 0:
                    deltas.append({
                        "label": "CPU Performance",
                        "winner_val": str(w_cpu),
                        "runner_val": str(r_cpu),
                        "delta_text": f"{abs(pct)}% slower CPU",
                        "status": "worse"
                    })
                    
            w_gpu = w_specs.get("gpu_score") or w_specs.get("gpu_score_3dmark")
            r_gpu = r_specs.get("gpu_score") or r_specs.get("gpu_score_3dmark")
            if w_gpu and r_gpu:
                pct = get_percent_delta(w_gpu, r_gpu)
                if pct > 0:
                    deltas.append({
                        "label": "GPU Capability",
                        "winner_val": str(w_gpu),
                        "runner_val": str(r_gpu),
                        "delta_text": f"{pct}% faster GPU",
                        "status": "better"
                    })
                elif pct < 0:
                    deltas.append({
                        "label": "GPU Capability",
                        "winner_val": str(w_gpu),
                        "runner_val": str(r_gpu),
                        "delta_text": f"{abs(pct)}% slower GPU",
                        "status": "worse"
                    })
                    
            w_bat = w_specs.get("battery_hours") or w_specs.get("estimated_office_hours")
            r_bat = r_specs.get("battery_hours") or r_specs.get("estimated_office_hours")
            if w_bat and r_bat:
                try:
                    diff = float(w_bat) - float(r_bat)
                    if diff > 0:
                        deltas.append({
                            "label": "Battery Life",
                            "winner_val": f"{w_bat} hrs",
                            "runner_val": f"{r_bat} hrs",
                            "delta_text": f"{round(diff, 1)} hours more battery",
                            "status": "better"
                        })
                    elif diff < 0:
                        deltas.append({
                            "label": "Battery Life",
                            "winner_val": f"{w_bat} hrs",
                            "runner_val": f"{r_bat} hrs",
                            "delta_text": f"{round(abs(diff), 1)} hours less battery",
                            "status": "worse"
                        })
                except (ValueError, TypeError):
                    pass
                    
            battle_comparison = {
                "runner_name": runner.product.name.split(" (")[0].strip(),
                "runner_sku": runner.product.sku,
                "winner_score": round(winner.score * 100, 1),
                "runner_score": round(runner.score * 100, 1),
                "deltas": deltas
            }

        # Build Funnel Metrics
        details = trace.get("pipeline_trace", [])
        total_compared = details[3].get("count", 0) if len(details) > 3 else len(products)
        funnel_metrics = {
            "total_compared": total_compared,
            "category_matched": details[0].get("count", total_compared) if len(details) > 0 else total_compared,
            "budget_passed": details[2].get("count", 0) if len(details) > 2 else 0,
            "constraints_passed": details[4].get("count", 0) if len(details) > 4 else 0,
            "ranked": len(trace.get("ranking", []))
        }

        # Run Sensitivity Analysis
        sensitivity_analysis = []
        rel_stability = 100.0
        
        # Parse soft attributes and budget
        soft_attrs = [attr for attr in engine.attributes if not attr.is_hard_filter]
        priorities = {}
        for attr in engine.attributes:
            if not attr.is_hard_filter:
                priorities[attr.key] = 3.0
        for ans in answers_summary:
            maps_to = ans.get("maps_to")
            val = ans.get("selected_value")
            if isinstance(val, dict):
                val = val.get("value")
            if maps_to and val is not None:
                try:
                    val_f = float(val)
                    if maps_to in priorities:
                        priorities[maps_to] = val_f
                except ValueError:
                    pass
        
        sorted_soft_attrs = sorted(soft_attrs, key=lambda attr: priorities.get(attr.key, 3.0), reverse=True)
        top_soft_attrs = sorted_soft_attrs[:3]
        
        # Parse budget
        budget_inr = None
        for ans in answers_summary:
            maps_to = ans.get("maps_to")
            val = ans.get("selected_value")
            if isinstance(val, dict):
                val = val.get("value")
            if maps_to == "price" and val is not None:
                try:
                    budget_inr = float(val)
                except ValueError:
                    pass
        
        # Lower budget simulation
        if budget_inr is not None:
            sim_answers = []
            for ans in answers_summary:
                if ans.get("maps_to") == "price":
                    sim_answers.append({**ans, "selected_value": {"value": budget_inr * 0.8}})
                else:
                    sim_answers.append(ans)
            
            sim_results, _, sim_status = engine.run(
                products,
                sim_answers,
                persona_hint=persona,
                custom_persona_weights=None,
                intent_confidence=100.0,
                currency_code=target_currency,
                currency_symbol=local_symbol,
                query=""
            )
            if sim_status == "success" and sim_results:
                sim_winner = sim_results[0].product
                if sim_winner.sku != winner.product.sku:
                    sensitivity_analysis.append({
                        "parameter": "price",
                        "trigger_condition": f"your budget drops below {local_symbol}{budget_inr * 0.8:,.0f}",
                        "alternative_winner_sku": sim_winner.sku,
                        "alternative_winner_name": sim_winner.name.split(" (")[0].strip()
                    })
        
        # Top soft attributes simulation
        for attr in top_soft_attrs:
            sim_answers = []
            found = False
            for ans in answers_summary:
                if ans.get("maps_to") == attr.key:
                    sim_answers.append({**ans, "selected_value": {"value": 5.0}})
                    found = True
                else:
                    sim_answers.append(ans)
            if not found:
                sim_answers.append({
                    "question_text": f"Importance of {attr.name}",
                    "selected_value": {"value": 5.0},
                    "maps_to": attr.key
                })
            
            sim_results, _, sim_status = engine.run(
                products,
                sim_answers,
                persona_hint=persona,
                custom_persona_weights=None,
                intent_confidence=100.0,
                currency_code=target_currency,
                currency_symbol=local_symbol,
                query=""
            )
            if sim_status == "success" and sim_results:
                sim_winner = sim_results[0].product
                if sim_winner.sku != winner.product.sku and sim_winner.sku not in [s["alternative_winner_sku"] for s in sensitivity_analysis]:
                    sensitivity_analysis.append({
                        "parameter": attr.key,
                        "trigger_condition": f"{attr.name} becomes a HIGH priority",
                        "alternative_winner_sku": sim_winner.sku,
                        "alternative_winner_name": sim_winner.name.split(" (")[0].strip()
                    })
        
        # Stability simulation for reliability
        sim_answers = []
        if len(top_soft_attrs) >= 2:
            highest_attr = top_soft_attrs[0]
            second_attr = top_soft_attrs[1]
            for ans in answers_summary:
                if ans.get("maps_to") == highest_attr.key:
                    val = priorities.get(highest_attr.key, 3.0)
                    sim_answers.append({**ans, "selected_value": {"value": max(1.0, val - 0.5)}})
                elif ans.get("maps_to") == second_attr.key:
                    val = priorities.get(second_attr.key, 3.0)
                    sim_answers.append({**ans, "selected_value": {"value": min(5.0, val + 0.5)}})
                else:
                    sim_answers.append(ans)
        else:
            sim_answers = answers_summary
        
        sim_results, _, sim_status = engine.run(
            products,
            sim_answers,
            persona_hint=persona,
            custom_persona_weights=None,
            intent_confidence=100.0,
            currency_code=target_currency,
            currency_symbol=local_symbol,
            query=""
        )
        if sim_status == "success" and sim_results:
            sim_winner = sim_results[0].product
            if sim_winner.sku != winner.product.sku:
                rel_stability = 80.0

        # Calculate Reliability Score & detailed breakdown
        matched_cnt = funnel_metrics["constraints_passed"]
        rel_intent = 95.0
        
        # Calculate distinct model metrics across evaluated candidates
        candidate_models = set()
        candidate_families = set()
        candidate_brands = set()
        for cand in scored_results:
            p = cand.product
            m_name = getattr(p, "model", None) or getattr(p, "name", "")
            f_name = getattr(p, "product_family", None) or getattr(p, "name", "")
            b_name = getattr(p, "brand", None) or p.specs.get("brand", "")
            if m_name: candidate_models.add(str(m_name).lower())
            if f_name: candidate_families.add(str(f_name).lower())
            if b_name: candidate_brands.add(str(b_name).lower())

        distinct_models_count = len(candidate_models)
        distinct_families_count = len(candidate_families)
        distinct_brands_count = len(candidate_brands)

        filled_specs = len([k for k, v in winner.product.specs.items() if v is not None])
        total_config_specs = max(1, len(config.attributes))
        rel_spec = min(100.0, (filled_specs / total_config_specs) * 100.0)
        
        # Competitive Catalog Coverage (Model-aware, not raw SKU variants)
        if distinct_models_count <= 0:
            rel_catalog = 0.0
        elif distinct_models_count == 1:
            rel_catalog = 20.0  # Single model candidate pool
        elif distinct_models_count == 2:
            rel_catalog = 45.0  # Only two models to compare
        elif distinct_models_count == 3:
            rel_catalog = 65.0
        elif distinct_models_count == 4:
            rel_catalog = 80.0
        else:
            rel_catalog = min(100.0, 80.0 + (distinct_models_count - 5) * 3.0)

        # Runner-up score margin
        if distinct_models_count >= 2 and len(scored_results) >= 2:
            margin = winner.score - scored_results[1].score
            rel_margin = min(100.0, 60.0 + margin * 350.0)
        else:
            # Low margin score if no distinct model alternative exists
            rel_margin = 25.0

        present_attrs = sum(1 for attr in config.attributes if engine._get_spec_val(winner.product, attr.key) is not None)
        rel_completeness = (present_attrs / len(config.attributes)) * 100.0 if config.attributes else 100.0
        
        rel_stability_score = float(rel_stability)
        raw_reliability = 0.20 * rel_intent + 0.15 * rel_spec + 0.20 * rel_catalog + 0.20 * rel_margin + 0.10 * rel_completeness + 0.15 * rel_stability_score

        # Apply Sparse Catalog Multiplier if distinct models are sparse
        if distinct_models_count <= 1:
            sparse_penalty = 0.65  # Cap single model reliability at ~45-55%
        elif distinct_models_count == 2:
            sparse_penalty = 0.82  # Cap 2-model reliability at ~65-75%
        else:
            sparse_penalty = 1.0

        reliability_score = round(min(100.0, raw_reliability * sparse_penalty), 1)
        
        reliability_reasons = []
        if rel_intent >= 90:
            reliability_reasons.append("Intent clearly understood")
        else:
            reliability_reasons.append("Ambiguous intent fallback")
            
        if rel_spec >= 80:
            reliability_reasons.append("Complete specifications coverage")
        else:
            reliability_reasons.append("Partial specifications coverage")
            
        if distinct_models_count <= 1:
            reliability_reasons.append("Limited catalog coverage for these requirements")
        else:
            reliability_reasons.append(f"{matched_cnt} eligible candidates ({distinct_models_count} distinct models) analyzed")

        if winner.score < 0.50:
            reliability_reasons.append("This is the strongest available option, but it is not a close match to all your preferences.")

        # Price verification and freshness attribution
        if winner.product.price_verified:
            reliability_reasons.append("Verified fresh INR market price")
        else:
            reliability_reasons.append("Unverified estimated INR MSRP")
        
        if distinct_models_count >= 2 and len(scored_results) >= 2:
            margin = winner.score - scored_results[1].score
            if margin >= 0.08:
                reliability_reasons.append("Clear advantage over runner-up")
            elif margin >= 0.03:
                reliability_reasons.append("Moderate advantage over runner-up")
            else:
                reliability_reasons.append("Narrow margin over runner-up")
        else:
            reliability_reasons.append("No distinct alternative models available")
            
        if rel_stability_score == 100.0:
            reliability_reasons.append("Recommendation is stable under priority changes")
        else:
            reliability_reasons.append("Recommendation changes under priority variations")
            
        reliability_breakdown = {
            "intent_confidence": rel_intent,
            "specification_coverage": rel_spec,
            "catalog_coverage": rel_catalog,
            "score_margin": rel_margin,
            "data_completeness": rel_completeness,
            "stability_score": rel_stability_score
        }

        # Build Detailed Confidence Breakdown
        win_margin = 90.0
        if len(alternatives) > 0:
            win_margin = min(100.0, max(50.0, 70.0 + (winner.score - alternatives[0].score) * 100.0))
            
        confidence_breakdown = {
            "category_detection": 100.0,
            "budget_match": 100.0,
            "spec_match": round(min(100.0, winner.score * 100 + 10), 1),
            "winner_margin": round(win_margin, 1),
            "catalog_coverage": 93.0
        }

        # Calculate use case ranking & domain scores
        from app.services.score_calculator import ScoreCalculator
        winner_domain_scores = ScoreCalculator.calculate_all(category, winner.product.specs, float(winner.product.price_inr))
        winner_domain_scores = {k.replace("_score", ""): round(v * 10, 1) for k, v in winner_domain_scores.items()}

        # Extract CPU and GPU values for percentiles
        all_cpus = []
        all_gpus = []
        for p in products:
            cpu_val = p.specs.get("cpu_score") or p.specs.get("cpu_multi_core") or p.specs.get("processor_score")
            gpu_val = p.specs.get("gpu_score") or p.specs.get("gpu_score_3dmark")
            if cpu_val is not None:
                try:
                    all_cpus.append(float(cpu_val))
                except (ValueError, TypeError):
                    pass
            if gpu_val is not None:
                try:
                    all_gpus.append(float(gpu_val))
                except (ValueError, TypeError):
                    pass

        w_cpu = winner.product.specs.get("cpu_score") or winner.product.specs.get("cpu_multi_core") or winner.product.specs.get("processor_score")
        w_gpu = winner.product.specs.get("gpu_score") or winner.product.specs.get("gpu_score_3dmark")

        def calculate_percentile(target_val, all_vals):
            if not all_vals or target_val is None:
                return 50.0
            try:
                target_float = float(target_val)
            except (ValueError, TypeError):
                return 50.0
            sorted_vals = sorted(all_vals)
            smaller = sum(1 for v in sorted_vals if v <= target_float)
            return round((smaller / len(sorted_vals)) * 100, 1)

        cpu_percentile = calculate_percentile(w_cpu, all_cpus) if w_cpu is not None else None
        gpu_percentile = calculate_percentile(w_gpu, all_gpus) if w_gpu is not None else None

        use_case = subcategory.lower() if subcategory else "gaming"
        score_key_map = {
            "gaming": "gaming_score",
            "developer": "programming_score",
            "programming": "programming_score",
            "creator": "creator_score",
            "business": "business_score",
            "student": "student_score",
            "general": "business_score"
        }
        target_score_key = score_key_map.get(use_case, "gaming_score")
        
        scored_pool = []
        for p in products:
            scores = ScoreCalculator.calculate_all(category, p.specs, float(p.price_inr))
            scored_pool.append((p.sku, scores.get(target_score_key, 0.0)))
        
        scored_pool.sort(key=lambda x: -x[1])
        winner_rank = 1
        for idx, (sku, score) in enumerate(scored_pool):
            if sku == winner.product.sku:
                winner_rank = idx + 1
                break

        details_meta = trace["pipeline_trace"][4].get("details", {})
        debug_trace = {
            "loaded_products": len(products),
            "subtype_products": details_meta.get("Subtype", 0),
            "budget_passed": details_meta.get("Budget", 0),
            "hard_constraints_passed": details_meta.get("Stock", 0),
            "mcda_candidates": details_meta.get("Stock", 0),
            "winner": winner.product.name,
            "winner_score": round(winner.score * 100, 1),
            "runner_up": alternatives[0].product.name if len(alternatives) > 0 else None,
            "runner_up_score": round(alternatives[0].score * 100, 1) if len(alternatives) > 0 else None,
            "reason": explanation.get("pros", [])[:2] + explanation.get("cons", [])[:1],
            "winner_scoring_breakdown": winner.scoring_breakdown,
            "alternatives_scoring_breakdown": [a.scoring_breakdown for a in alternatives]
        }
        trace["debug_trace"] = debug_trace

        structured_analysis = {
            "pros": explanation["pros"],
            "cons": explanation["cons"],
            "tradeoffs": tradeoffs,
            "reasoning": explanation["reasoning"],
            "summary": explanation["summary"],
            "citations": explanation["citations"],
            "local_price": winner_local_price,
            "local_currency": target_currency,
            "local_symbol": local_symbol,
            "funnel_metrics": funnel_metrics,
            "confidence_breakdown": confidence_breakdown,
            "decision_trace": trace,
            "debug_trace": debug_trace,
            "domain_scores": winner_domain_scores,
            "component_percentiles": {
                "cpu": cpu_percentile,
                "gpu": gpu_percentile
            },
            "use_case_rank": {
                "rank": winner_rank,
                "total": len(products),
                "name": use_case.capitalize()
            },
            "reliability_score": reliability_score,
            "reliability_reasons": reliability_reasons,
            "battle_comparison": battle_comparison,
            "upgrade_analysis": upgrade_analysis,
            "spend_less_analysis": spend_less_analysis,
            "sensitivity_analysis": sensitivity_analysis,
            "reliability_breakdown": reliability_breakdown,
            "user_preferences": {
                "category": category,
                "subcategory": subcategory,
                "detected_use_case": persona,
                "answers": [
                    {
                        "question_text": ans["question_text"],
                        "selected_value": ans["selected_value"],
                        "maps_to": ans["maps_to"]
                    } for ans in answers_summary
                ]
            }
        }

        # Run read-only Decision Invariant Auditor
        payload_for_audit = {
            "verdict_product": {
                "id": str(winner.product.id),
                "sku": winner.product.sku,
                "name": winner.product.name,
                "price": float(winner.product.price_inr),
                "specs": winner.product.specs
            },
            "score": float(winner.score),
            "confidence": float(winner.confidence_score)
        }
        audit_status, audit_violations = DecisionInvariantAuditor.audit(
            payload_for_audit,
            structured_analysis,
            engine,
            config
        )
        structured_analysis["decision_trace"]["audit_status"] = audit_status
        structured_analysis["decision_trace"]["audit_violations"] = audit_violations

        # 2-Tier audit tracing (full_audit_trace for dev/debug only)
        full_audit_trace = {
            "raw_scores": [
                {
                    "sku": cand.product.sku,
                    "name": cand.product.name,
                    "score": float(cand.score),
                    "normalized_values": getattr(cand, 'normalized_values', {}),
                    "raw_values": getattr(cand, 'raw_values', {}),
                    "scoring_breakdown": getattr(cand, 'scoring_breakdown', {})
                } for cand in scored_results
            ],
            "pareto_evidence": trace.get("pareto_analysis", {}).get("dominated_products", []),
            "explanation_evidence": explanation.get("evidence", []),
            "guardrail_log": trace.get("guardrail_results", {})
        }
        structured_analysis["full_audit_trace"] = full_audit_trace

        # Model-Level Image Inheritance
        winner_img_url = winner.product.image_url
        winner_img_match = winner.product.image_match_level
        winner_img_verified = winner.product.image_verified

        if not winner_img_url and winner.product.model:
            stmt_img = select(Product.image_url, Product.image_match_level, Product.image_verified).where(
                Product.model == winner.product.model,
                Product.image_url.isnot(None),
                Product.image_url != ""
            ).limit(1)
            img_res = await self.session.execute(stmt_img)
            fallback_img = img_res.first()
            if fallback_img:
                winner_img_url, winner_img_match, winner_img_verified = fallback_img[0], fallback_img[1], True

        verdict_product_data = {
            "id": str(winner.product.id),
            "sku": winner.product.sku,
            "name": winner.product.name,
            "category": winner.product.category,
            "brand": winner.product.brand,
            "model": winner.product.model,
            "price_inr": float(winner.product.price_inr),
            "specs": winner.product.specs,
            "image_url": winner_img_url,
            "image_match_level": winner_img_match,
            "image_verified": winner_img_verified,
            "source_type": winner.product.source_type,
            "created_at": winner.product.created_at.isoformat() if winner.product.created_at else None
        }

        return {
            "id": None,
            "decision_id": None,
            "verdict_product_id": str(winner.product.id),
            "verdict_product": verdict_product_data,
            "confidence_score": winner.confidence_score,
            "structured_analysis": structured_analysis,
            "explanation_md": explanation["summary"] + "\n\n" + explanation["reasoning"]
        }

