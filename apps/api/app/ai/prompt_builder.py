from typing import Dict, Any, List
from app.ai.schemas import PromptContext

class PromptBuilder:
    """Assembles context-rich system instructions and prompts for the Gemini Provider."""

    @staticmethod
    def build_system_instruction() -> str:
        return (
            "You are the Nexus Decision Explainer, an AI that translates mathematical scoring matrix "
            "verdicts into clear, conversational product recommendations.\n"
            "You will be given the user's questionnaire answers, the highest scoring product (the verdict), "
            "the runner-up alternative options, and a calculated tradeoffs comparison dataset.\n\n"
            "Your instructions:\n"
            "1. Output a JSON object matching the requested schema.\n"
            "2. Under 'pros', list 3 bullet points showing how the winner matches the user's specific answers.\n"
            "3. Under 'cons', list 1-2 points showing the winner's drawbacks relative to other catalog options.\n"
            "4. Under 'reasoning', explain why this product won using the mathematical score and tradeoffs data.\n"
            "5. Under 'summary', write a friendly 2-sentence conclusion recommending this product.\n"
            "6. Stick strictly to facts in the specifications. Do not hallucinate values."
        )

    @staticmethod
    def build_prompt(context: PromptContext) -> str:
        # Format user responses
        answers_str = "\n".join(
            f"- Question: \"{ans['question_text']}\" -> Answer value: {ans['selected_value'].get('value')}"
            for ans in context.answers_summary
        )

        # Format winning product
        verdict = context.verdict_product
        specs_list = []
        for k, v in verdict.get("specs", {}).items():
            specs_list.append(f"  * {k}: {v}")
        verdict_specs_str = "\n".join(specs_list)

        # Format runner-ups
        alts_list = []
        for alt in context.alternatives:
            alt_specs = "\n".join(f"    * {k}: {v}" for k, v in alt.get("specs", {}).items())
            alts_list.append(
                f"- Name: {alt['name']}\n"
                f"  SKU: {alt['sku']}\n"
                f"  Price: Rs {alt['price_inr']:.2f}\n"
                f"  Specs:\n{alt_specs}"
            )
        alts_str = "\n".join(alts_list)

        # Format tradeoffs
        tradeoffs_list = []
        for t in context.tradeoffs:
            deltas_list = []
            for d in t.get("deltas", []):
                deltas_list.append(f"    * {d['attribute']}: {d['description']} ({d['direction']})")
            deltas_str = "\n".join(deltas_list)
            tradeoffs_list.append(
                f"- Alternative option: {t['alternative_name']} (SKU: {t['alternative_sku']})\n"
                f"  Deltas vs Winner:\n{deltas_str}"
            )
        tradeoffs_str = "\n".join(tradeoffs_list)

        return (
            f"User Session Profile: {context.decision_title}\n"
            f"User Submitted Answers:\n{answers_str}\n\n"
            f"--- MATCH VERDICT DETAILS ---\n"
            f"Verdict Product SKU: {verdict['sku']}\n"
            f"Verdict Product Name: {verdict['name']}\n"
            f"Verdict Product Price: Rs {verdict['price_inr']:.2f}\n"
            f"Verdict Score: {context.verdict_score:.2f}\n"
            f"Confidence: {context.confidence_score:.1f}%\n"
            f"Verdict Specifications:\n{verdict_specs_str}\n\n"
            f"--- ALTERNATIVES MATCH LIST ---\n{alts_str}\n\n"
            f"--- TRADEOFF ANALYSIS DELTAS ---\n{tradeoffs_str}\n"
        )
