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
        try:
            from app.services.catalog_enricher import CatalogEnricher
            enricher = CatalogEnricher(self.session)
            enriched_count = await enricher.enrich_catalog(
                query=decision.title, 
                category=decision.category, 
                currency=target_currency
            )
            # Commit the catalog enrichment immediately to release the SQLite write lock
            await self.session.commit()
            logger.info("Catalog enrichment completed successfully", count=enriched_count)
        except Exception as e:
            await self.session.rollback()
            logger.error("Catalog enrichment step failed, proceeding with local catalog", error=str(e))


        # 4. Query search providers interface (CatalogProvider)
        provider = LocalCatalogProvider(self.session)
        products = await provider.get_products(decision.category)
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
                "closest_matches": trace["closest_matches"]
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
            "decision_trace": trace
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
