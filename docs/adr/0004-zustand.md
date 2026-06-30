# Architecture Decision Record (ADR) 0004: Zustand for Client-Side State

## Context
Nexus features interactive UI modules like the **Copilot Drawer** (which requires toggling open/close states and appending streaming message histories across routes) and the **Decision Sandbox** (which tracks real-time slider weights and computes temporary score deltas). We need a client-side state manager that:
1. Prevents unnecessary component re-renders.
2. Avoids the complex boilerplate of Redux.
3. Bypasses the render performance bottlenecks of React Context (which re-renders all children when context values change).

## Decision
We will use **Zustand** for all global client-side UI and transient application state.

## Alternatives Considered
1. **Redux Toolkit**:
   - *Pros*: Highly structured, widely used, excellent debugging middleware.
   - *Cons*: Heavy boilerplate (actions, reducers, selectors, configureStore) which increases code complexity for small UI state needs.
2. **React Context API**:
   - *Pros*: Built into React, no external package dependency.
   - *Cons*: When a Context value changes, all components consuming the context re-render. Mitigating this requires splitting context into multiple providers, leading to a complex "wrapper hell" structure in root layouts.
3. **Jotai / Recoil (Atomic State)**:
   - *Pros*: Excellent for canvas-like interfaces.
   - *Cons*: Slightly higher learning curve than Zustand's simple hook-based store. Zustand is simpler and integrates well with React lifecycle methods.

## Trade-Offs & Consequences
* **Pros**:
  - **No Provider Wrappers**: State is initialized in simple stores outside the React render tree. Component hooks subscribe only to selected slices of the state, preventing unnecessary re-renders.
  - **Minimal Boilerplate**: A store is defined in a few lines of code.
  - **Native TypeScript Support**: Types are inferred cleanly.
* **Cons**:
  - **Unstructured Freedom**: Since Zustand does not force strict patterns (like Redux actions), developers could write direct state modifications across different directories. We mitigate this by keeping stores inside `src/stores/` and using defined set actions instead of raw state modifications.
