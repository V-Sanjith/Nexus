import asyncio
from uuid import UUID
from typing import Optional, Dict, Any, List
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
        
        is_no_match = (status == "no_match_found")
        
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
        
        # Calculate Reliability Score & Reasons
        reliability_reasons = []
        if decision.intent_confidence and decision.intent_confidence >= 90:
            reliability_reasons.append("High confidence intent detection")
        else:
            reliability_reasons.append("Moderate confidence intent detection")
            
        spec_keys_checked = len([k for k in winner.product.specs.keys() if winner.product.specs[k] is not None])
        spec_factor = spec_keys_checked / max(1, len(config.attributes))
        if spec_factor >= 0.8:
            reliability_reasons.append("Complete specifications coverage")
        else:
            reliability_reasons.append("Partial specifications coverage")
            
        if len(alternatives) > 0:
            margin = winner.score - alternatives[0].score
            if margin >= 0.08:
                reliability_reasons.append("Strong margin over runner-up")
            elif margin >= 0.03:
                reliability_reasons.append("Clear margin over runner-up")
            else:
                reliability_reasons.append("Narrow margin over runner-up")
        else:
            reliability_reasons.append("No comparable runner-up found")
            
        matched_cnt = funnel_metrics["constraints_passed"]
        reliability_reasons.append(f"{matched_cnt} matching products available")
        
        rel_det = float(decision.intent_confidence or 95.0)
        rel_spec = min(100.0, spec_factor * 100.0)
        rel_margin = 100.0 if (len(alternatives) > 0 and (winner.score - alternatives[0].score) >= 0.05) else 85.0
        rel_pool = min(100.0, 70.0 + min(30.0, matched_cnt * 2.0))
        
        reliability_score = round((rel_det + rel_spec + rel_margin + rel_pool) / 4.0, 1)

        # Build Runner-Up Battle Comparison
        battle_comparison = None
        if len(alternatives) > 0:
            runner = alternatives[0]
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

        # Build Upgrade / Worth Upgrading Analysis
        upgrade_analysis = None
        if len(alternatives) > 0:
            more_expensive = [alt for alt in alternatives if float(alt.product.price_inr) > winner_local_price]
            if more_expensive:
                target_up = min(more_expensive, key=lambda x: float(x.product.price_inr))
                up_price = float(target_up.product.price_inr)
                price_diff = up_price - winner_local_price
                
                up_gains = []
                w_specs = winner.product.specs
                u_specs = target_up.product.specs
                
                if u_specs.get("ram_gb", 0) > w_specs.get("ram_gb", 0):
                    up_gains.append(f"{u_specs.get('ram_gb')}GB RAM (vs {w_specs.get('ram_gb')}GB)")
                if u_specs.get("storage_gb", 0) > w_specs.get("storage_gb", 0):
                    up_gains.append(f"{u_specs.get('storage_gb')}GB SSD (vs {w_specs.get('storage_gb')}GB)")
                
                w_cpu = w_specs.get("cpu_score") or w_specs.get("cpu_multi_core") or w_specs.get("processor_score")
                u_cpu = u_specs.get("cpu_score") or u_specs.get("cpu_multi_core") or u_specs.get("processor_score")
                if w_cpu and u_cpu and float(u_cpu) > float(w_cpu):
                    up_gains.append("Faster CPU")
                    
                w_gpu = w_specs.get("gpu_score") or w_specs.get("gpu_score_3dmark")
                u_gpu = u_specs.get("gpu_score") or u_specs.get("gpu_score_3dmark")
                if w_gpu and u_gpu and float(u_gpu) > float(w_gpu):
                    up_gains.append("Faster GPU")
                    
                if target_up.score > winner.score + 0.05:
                    rec_verdict = f"Highly recommended upgrade if you have the budget, as it yields major suitability gains."
                else:
                    rec_verdict = f"Not worth upgrading unless you specifically need: {', '.join(up_gains[:2]) or 'the spec increase'}."
                    
                upgrade_analysis = {
                    "sku": target_up.product.sku,
                    "name": target_up.product.name.split(" (")[0].strip(),
                    "price": up_price,
                    "extra_cost": price_diff,
                    "gains": up_gains,
                    "verdict": rec_verdict
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
        category = payload.category.lower()
        subcategory = payload.subcategory.lower()
        persona = payload.persona.lower()
        target_currency = payload.currency.lower()
        local_symbol = "₹" if target_currency == "inr" else "$"

        # Load dynamic merged configuration
        registry = CategoryRegistry()
        config = registry.get(category, subcategory)
        if not config:
            raise ValueError(f"Category configuration for {category} not found.")

        # Match questions with answers to build answers_summary
        answers_summary = []
        for ans in payload.answers:
            q_id = ans.question_id
            # Find matching question in config
            q_cfg = None
            for q in config.questions:
                if q.order_index == q_id:
                    q_cfg = q
                    break
            
            if q_cfg:
                answers_summary.append({
                    "question_id": str(q_id),
                    "question_text": q_cfg.question_text,
                    "input_type": q_cfg.input_type,
                    "selected_value": ans.selected_value,
                    "question": {
                        "question_text": q_cfg.question_text,
                        "input_type": q_cfg.input_type,
                        "weight_impact": {"maps_to": q_cfg.maps_to}
                    },
                    "maps_to": q_cfg.maps_to
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
            "reason": explanation.get("pros", [])[:2] + explanation.get("cons", [])[:1]
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
            "decision_trace": trace,
            "debug_trace": debug_trace
        }

        # Format verdict_product for response
        verdict_product_data = {
            "id": str(winner.product.id),
            "sku": winner.product.sku,
            "name": winner.product.name,
            "category": winner.product.category,
            "price_inr": float(winner.product.price_inr),
            "specs": winner.product.specs,
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

