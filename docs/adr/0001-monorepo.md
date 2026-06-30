# Architecture Decision Record (ADR) 0001: Monorepo Workspace Structure

## Context
Nexus is composed of multiple subsystems: a Next.js web application, a FastAPI backend service, shared TS types, a shared UI library, and operational tooling configurations. Historically, keeping these in separate repositories leads to:
1. Version mismatch issues between APIs and clients.
2. Duplicate type definitions and design system code.
3. Complex developer environment setup steps.
4. Fragmented CI/CD pipelines.

We need a code organization pattern that supports dependency sharing, atomic commits across subsystems, and fast developer onboarding.

## Decision
We will use a **pnpm workspaces monorepo** managed by **Turborepo**. 

The folder structure is:
```
nexus/
├── apps/            # Deployable applications (web, api)
├── packages/        # Shared domain packages (types, ui, prompts)
├── tooling/         # Centralized development configurations (eslint, typescript)
└── docs/            # Product design and architecture logs
```

## Alternatives Considered
1. **Multi-Repo Layout**:
   - *Pros*: Independent repository structures, separate access controls.
   - *Cons*: High overhead for tracking API breaking changes; duplicate typing definitions; slow feature shipping due to multiple Pull Requests.
2. **Lerna / Yarn Workspaces**:
   - *Pros*: Traditional standard for monorepos.
   - *Cons*: Yarn is slower than pnpm at resolving dependencies. Lerna adds unnecessary publishing wrappers that are redundant for a private SaaS project.

## Trade-Offs & Consequences
* **Pros**:
  - **Single Source of Truth**: Shared code (types, components) is updated locally and immediately visible to all applications without requiring npm registry releases.
  - **Atomic Commits**: API model upgrades and corresponding frontend adjustments can be committed in a single Pull Request.
  - **Shared Toolchain**: ESLint, TypeScript, and Prettier presets are declared in `tooling/` and inherited by all modules, keeping code styling identical.
* **Cons**:
  - **Repository Size**: All application and packages code lives in a single repository, which increases download times for fresh checkouts (mitigated by using thin git clones and pnpm's global content store).
  - **Accidental Coupling**: Developers might bypass dependencies and couple modules (e.g., importing react files into api directories). We mitigate this by enforcing strict lint boundaries.
