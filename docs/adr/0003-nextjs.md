# Architecture Decision Record (ADR) 0003: Next.js 15 App Router

## Context
The Nexus web client requires a premium user experience featuring smooth transitions (Framer Motion), fast load times, and dynamic SEO-optimized public report sheets. We need a frontend engine that:
1. Minimizes initial JavaScript bundles (performance first).
2. Supports hybrid page routing (static pages for marketing, server-rendered views for share links, client-side dynamic views for the dashboard).
3. Easily handles edge redirection and API proxying (BFF).

## Decision
We will use **Next.js 15 (App Router)** as our primary frontend web platform.

## Alternatives Considered
1. **Single Page Application (Vite + React)**:
   - *Pros*: Simple routing, client-only bundles, no server middleware overhead.
   - *Cons*: Poor search engine optimization (SEO) for shared reports. Lack of native Server Components means the initial load requires rendering massive JS bundles, leading to slow Time-to-Interactive (TTI) scores on mobile screens.
2. **Remix**:
   - *Pros*: Excellent data-mutation models, focus on web standards.
   - *Cons*: Less ecosystem integration for modern tools like React Server Components (RSC) compared to Next.js. Next.js is the native choice for React 19 and integrates cleanly with Vercel's caching layer.

## Trade-Offs & Consequences
* **Pros**:
  - **React Server Components (RSC)**: Renders non-interactive HTML segments on the server side, keeping heavy libraries out of the browser bundle.
  - **Built-in BFF**: Next.js route handlers secure cookies, handle session validation, and proxy API calls to FastAPI, removing the need for a separate Node gateway layer.
  - **SEO & OG Image Gen**: Dynamic OpenGraph image generation is handled natively at the edge, creating social previews for shared reports.
* **Cons**:
  - **Complexity of Server/Client boundaries**: Developers must understand the distinction between Server and Client Components, passing Server Components as `children` to prevent client-side bundle leaks. We mitigate this by establishing clear component architecture rules.
