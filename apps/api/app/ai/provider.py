from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

class BaseLLMProvider(ABC):
    """Abstract base class defining LLM provider client interactions."""

    @abstractmethod
    async def generate_json(self, system_instruction: str, prompt: str, schema: Any) -> Dict[str, Any]:
        """
        Executes a call to the LLM to get structured JSON output.
        Fails or raises error if the response doesn't conform to the schema.
        """
        pass
