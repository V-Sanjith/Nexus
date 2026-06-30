# Architecture Decision Record (ADR) 0007: Google Gemini for core LLM operations

## Context
As an AI-powered decision engine, Nexus needs an LLM to:
1. Compile dynamic, category-specific question flows based on user profiles.
2. Analyze user priorities and write detailed, structured markdown explanations.
3. Classify user behavior to compute their Decision DNA profiles.
4. Execute real-time research query extraction.

We need an LLM model with fast execution, large context windows, low token costs, and structured JSON output capabilities.

## Decision
We will use **Google Gemini API** (using `Gemini 1.5 Pro` for complex analysis/reasoning and `Gemini 1.5 Flash` for fast question generation and parsing tasks).

## Alternatives Considered
1. **OpenAI GPT-4o / GPT-4o-mini**:
   - *Pros*: Excellent performance, mature ecosystem integration.
   - *Cons*: Higher token cost compared to Gemini Flash. The context window is limited to 128K tokens, which is smaller than Gemini's 1M+ limit, restricting our ability to ingest large specifications documents in context.
2. **Anthropic Claude 3.5 Sonnet**:
   - *Pros*: Excellent code generation and logical reasoning.
   - *Cons*: Highest token costs among primary providers. Lacks native multi-model billing efficiency (like Gemini's Flash/Pro tiering) for high-frequency small requests.
3. **Self-Hosted Open Source Models (Llama-3 via Ollama/vLLM)**:
   - *Pros*: Full control over parameters, high privacy, zero token costs.
   - *Cons*: Heavy infrastructure hosting costs (GPUs) and complex deployment operations. It is better to use managed APIs for the initial product launch and consider self-hosting open-source models later if needed.

## Trade-Offs & Consequences
* **Pros**:
  - **Context Window**: Gemini's 1-million-token context window allows us to pass large specification logs and user histories directly in prompt contexts.
  - **Flash/Pro Tiering**: Using Gemini Flash for simple tasks (question generation, parsing) and routing complex reasoning to Gemini Pro keeps operational costs low.
  - **Structured Schema Enforcement**: Built-in support for structured JSON schema outputs ensures the model's responses conform exactly to our Pydantic schemas, reducing parser failures.
* **Cons**:
  - **API Dependency**: We rely on Google's API availability. We mitigate this by using a retry wrapper with exponential backoff and caching prompt responses in Redis.
