# Tech Stack & Integration Standards

## Core Infrastructure Philosophy
The empire tech stack must be **modular, observable, and leverage-oriented**. Every component should either generate data for the flywheel, reduce manual work, or be teachable through Magic Layer. Complexity is only justified when it creates clear, compounding advantage across pillars.

## Primary Technology Stack

### Data Layer
- **Supabase (Postgres)**: Single source of truth for the empire.
  - Jobs, estimates, photos, clients, and structured operational data live here.
  - Future: Empire-wide tables for content assets, case studies, and cross-pillar metrics.
- **Knowledge Base**: Three-layer system stored in `/knowledge-base/`
  - **Raw**: Unstructured field data, photos, logs, chat history.
  - **Wiki**: Synthesized principles and constraints (this folder).
  - **Schema**: Structured models and data definitions.

### Frontend
- **React / Next.js**: Knight Dashboard and future empire interfaces.
  - Must remain lightweight and mobile-first.
  - Photo upload and real-time estimate flows are priority surfaces.

### Backend & Automation
- **Python**: Primary language for agents, engines, and orchestration.
  - Key modules: `empire_ai_nexus.py`, `crewroute_daily_engine.py`, `photo_audit_agent.py`, `solo_pilot_agent.py`, `focus_mode_agent.py`.
- **Telegram Bot**: Primary notification and lightweight command surface for field operations.

### AI Layer
- **Claude (primary)**: Used for reasoning, vision analysis, code generation, and strategic work.
- **Empire Behavioral Prompt**: Must be loaded at the start of every session (see `empire-behavioral-prompt.md`).
- **Dynamic Context Injection**: Handled by `empire_ai_nexus.py` — automatically assembles relevant wiki pages based on task context.
- **Vision**: Claude Vision for photo analysis and proof-of-work validation.

### Mapping & Optimization
- **Google Maps API** + **OR-Tools**: Routing, clustering, and dispatch optimization (in active development).
- Goal: Move from manual routing to AI-assisted dynamic dispatch.

### Knowledge & Documentation
- **Obsidian-compatible Markdown**: All wiki and raw knowledge stored in `/knowledge-base/`.
- **Empire Nexus**: `empire_ai_nexus.py` acts as the intelligent context router that feeds the correct wiki pages to the LLM before work begins.

## Agent Philosophy

Agents must follow these standards:

- **Modular by default** — Each agent has a single, clear responsibility.
- **Knowledge-aware** — Every agent must reference the Empire Knowledge Base before acting.
- **Nexus-orchestratable** — Agents are designed to be called or composed by `empire_ai_nexus.py`.
- **Observable** — All significant actions and decisions should be logged in a way that can feed back into the Raw → Wiki → Schema loop.
- **Leverage-focused** — Prefer agents that remove recurring manual work over one-off scripts.

Current core agents:
- `photo_audit_agent.py` — Photo analysis and quality/compliance validation.
- `solo_pilot_agent.py` — Support for solo operator decision-making and task execution.
- `focus_mode_agent.py` — Deep work prioritization and context protection.
- `empire_ai_nexus.py` — Context router and session initializer (the central nervous system).

## Integration Standards

- **Mandatory Session Start**: Every AI session must begin by loading the Empire Behavioral Prompt + relevant wiki context via the Nexus.
- **Data Flow**: Field photos and job data → Supabase → Knowledge Base → Improved future estimates and content.
- **Cross-Pillar Awareness**: The stack must support easy extraction of CJS operational data for Triple C content and Magic Layer case studies.
- **Deployment**: Railway (via `railway.toml`) for backend services. Keep deployment simple and reproducible.

## Current Limitations & Active Development Areas

- Google Maps + OR-Tools routing logic is still early.
- Full photo → structured job record pipeline needs production hardening.
- `empire_ai_nexus.py` is functional but needs deeper integration with the new Empire Knowledge Base structure.
- Limited mobile field interface (currently relies on dashboard + Telegram).

## Long-Term Direction (Post June 2026)

- Evolve `empire_ai_nexus.py` into a true multi-agent orchestrator.
- Build a unified Empire Dashboard that surfaces CJS operations, Triple C impact, and Magic Layer progress.
- Create reusable agent templates that can be taught in Magic Layer.
- Prepare the stack for reduced direct oversight once Maestro College begins.

## Non-Negotiables

- Supabase remains the single source of truth.
- The Empire Behavioral Prompt + Knowledge Base must be loaded before any significant work.
- All new agents or features must be designed with modularity and cross-pillar leverage in mind.