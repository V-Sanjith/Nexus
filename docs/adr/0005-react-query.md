# Architecture Decision Record (ADR) 0005: TanStack React Query for Server State

## Context
Client Components in Nexus must fetch, update, and invalidate data (decisions, specs, user preferences, timeline items) from the database via the API gateway. Managing this manually leads to:
1. Complex loading/error states in every component.
2. Redundant API requests (e.g. fetching the same profile data on multiple pages).
3. Out-of-sync UI states (e.g. submitting a new decision but the history list doesn't update).

We need a dedicated caching and query coordinator for server data.

## Decision
We will use **TanStack React Query** (v5) to manage all client-side server state queries, mutations, and caching configurations.

## Alternatives Considered
1. **Manual `useEffect` Fetching**:
   - *Pros*: Zero external dependencies.
   - *Cons*: High boilerplate. Developers must manually manage loading, error, caching, race conditions, and retry behaviors, leading to inconsistent implementations.
2. **RTK Query (Redux)**:
   - *Pros*: Powerful, integrates directly with Redux.
   - *Cons*: Requires setting up Redux, which is overkill since we have chosen Zustand for local state.

## Trade-Offs & Consequences
* **Pros**:
  - **Automated Caching**: Identical API queries within their TTL reuse cache memory, preventing duplicate network requests.
  - **State Simplification**: Provides built-in `isLoading`, `isError`, and `data` objects, removing manual state variables.
  - **Optimistic Updates**: Enables updating the UI instantly when submitting answers or changing sliders, resolving mutations in the background and rolling back if the network fails.
* **Cons**:
  - **Client Bundle Cost**: Adds ~10KB to the JavaScript bundle size.
  - **Cache Invalidation Overhead**: Developers must define correct query keys (e.g. `['decisions', id]`) and explicitly call invalidation triggers (`queryClient.invalidateQueries`) to keep local caches in sync with backend database mutations.
