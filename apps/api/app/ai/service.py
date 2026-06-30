from typing import Optional
from app.ai.provider import BaseLLMProvider
from app.ai.gemini import GeminiProvider
from app.ai.prompt_builder import PromptBuilder
from app.ai.output_parser import OutputParser
from app.ai.schemas import PromptContext, StructuredRecommendation

class AIService:
    """Coordinates prompt construction, LLM client execution, and output parsing."""

    def __init__(self, provider: Optional[BaseLLMProvider] = None):
        self.provider = provider or GeminiProvider()

    async def generate_recommendation_justification(self, context: PromptContext) -> StructuredRecommendation:
        """Assembles prompt and invokes provider to produce structured AI recommendations."""
        system_instruction = PromptBuilder.build_system_instruction()
        prompt = PromptBuilder.build_prompt(context)

        # Call isolated provider
        raw_output = await self.provider.generate_json(
            system_instruction=system_instruction,
            prompt=prompt,
            schema=StructuredRecommendation
        )

        # Parse and validate response
        return OutputParser.parse_recommendation(raw_output)
