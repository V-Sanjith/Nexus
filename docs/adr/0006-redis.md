# Architecture Decision Record (ADR) 0006: Redis for Session Caching & Rate Limiting

## Context
Nexus is designed to handle high concurrency. Every incoming request must verify the user's session validity. Fetching session validation records from the primary database (PostgreSQL) on every single API request creates a performance bottleneck. Additionally:
1. Public AI generation and scraping routes are vulnerable to DDoS attacks and scraping resource abuse.
2. SSE recommendation channels need transient message buffers.
3. Prompt compilation requires caching to avoid redundant filesystem operations.

We need a low-latency cache database.

## Decision
We will use **Redis** (version 7.x) as an in-memory key-value database, serving as our session store, API rate-limiter, feature flag cache, and message queue broker.

## Alternatives Considered
1. **In-Memory Application Caches (FastAPI Global variables)**:
   - *Pros*: Zero external dependencies, extremely fast.
   - *Cons*: Cache memory is isolated to a single container. As soon as the backend scales horizontally, the caches become out-of-sync.
2. **Memcached**:
   - *Pros*: Simple, fast, multithreaded.
   - *Cons*: Strictly key-value; lacks advanced data structures (Hashes, Sorted Sets, Pub/Sub channels) which we require for SSE message streaming and sliding-window rate limiters.

## Trade-Offs & Consequences
* **Pros**:
  - **Latency**: Operations run in sub-millisecond ranges, keeping auth checks extremely fast.
  - **Advanced Structures**: Redis Hashes (for feature flags) and Sorted Sets (for sliding-window rate limiting) simplify backend logic.
  - **Expiry Mechanics**: Built-in TTL automatically sweeps expired sessions and rate limit windows.
* **Cons**:
  - **Data Volatility**: Since Redis stores data in RAM, crashes or restarts can result in data loss unless configured with disk backup replication (AOF/RDB). This is fine because Redis is only used for temporary caches, session tokens, and rate limits. Primary persistent data remains safely stored in PostgreSQL.
