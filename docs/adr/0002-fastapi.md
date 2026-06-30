# Architecture Decision Record (ADR) 0002: FastAPI for Backend API

## Context
The Nexus backend requires high-performance execution of multi-criteria mathematical evaluations (the Decision Engine) and frequent integration with AI endpoints (Google Gemini API). It must support:
1. Asynchronous networking (for SSE recommendation streaming).
2. Strict type validation at the API boundaries (schema enforcement).
3. Fast execution speed.
4. Smooth integration with Python's data science and LLM libraries.

## Decision
We will use **FastAPI** (Python 3.10+) with **Pydantic v2** and **SQLAlchemy** for database async transactions. We will use **`uv`** as the Python package manager.

## Alternatives Considered
1. **Node.js (Express / NestJS)**:
   - *Pros*: Single language (JavaScript/TypeScript) across both frontend and backend.
   - *Cons*: Weak ecosystem for advanced data analysis and custom mathematical modeling. Integrating Gemini streaming works, but downstream scraping, spec matching, and data science utilities would require microservice hand-offs to Python anyway.
2. **Django**:
   - *Pros*: Highly mature, built-in admin panel, battery-included ORM.
   - *Cons*: Sync-by-default architecture makes Django slow when handling thousands of concurrent open Server-Sent Event (SSE) streams. Adding Django Channels introduces heavy system overhead (Redis channel layers) that FastAPI handles natively.

## Trade-Offs & Consequences
* **Pros**:
  - **Asynchronous Execution**: Native `async`/`await` support allows handling thousands of concurrent streaming connections on minimal resource configurations.
  - **Auto-generated Documentation**: Pydantic models automatically compile to OpenAPI specs, exposing `/docs` (Swagger UI) instantly.
  - **Type Safety**: Combining Python type hints with Pydantic ensures data entering the API is validated before execution, preventing database type errors.
* **Cons**:
  - **Polyglot Monorepo Complexity**: Developers must work in both TypeScript (Next.js) and Python (FastAPI). This is mitigated by using code-generation pipelines that compile OpenAPI schemas directly to TypeScript interfaces, keeping contracts synchronized automatically.
