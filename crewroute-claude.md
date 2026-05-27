# CrewRoute AI OS — Behavioral System Rules

This file governs all LLM reasoning, code generation, and file-editing behaviors for CrewRoute OS. Load this file at the start of every session.

## Core Behavioral Rules

1. **Architectural Thinking**  
   Prioritize modularity, long-term leverage, and moat-building. Think in systems, not just features.

2. **Data Integrity**  
   Never hallucinate formulas or constraints. Always reference `/knowledge-base/wiki/` files first.

3. **Compact Feedback**  
   Be direct, no-fluff, and actionable. Avoid padding or overly verbose explanations.

4. **Auto-Research Loop**  
   Check relevant wiki pages and raw data before proposing solutions. Validate assumptions against real field data.

## Financial Engine (v0.3) — Non-Negotiable

- **Base Labor Rate**: $65/hr
- **Target Margin**: 35%
- **Estimating Formula**:  
  `Base Hours = SqFt / 1600`  
  `Base Cost = Base Hours × $65`  
  `Total Price = Base Cost / (1 - 0.35)`
- **Commercial Upsell Target**: 1.54x material markup

## Operational Constraints

- **Pacific Beach (PB)**: High-density properties, solo crews, tight 07:00–09:00 arrival windows, parking challenges.
- **North County**: Wider transit areas, multi-crew potential, I-5 corridor clustering opportunities.
- **Safety & Compliance**: All field operations must eventually align with OSHA standards and VA prevailing wage requirements for government work.

## Tech Stack & Integration Rules

- **Data Layer**: Supabase (Postgres) is the single source of truth for jobs, estimates, photos, and clients.
- **Mapping & Routing**: Google Maps API + OR-Tools for optimization.
- **Knowledge System**: Obsidian-compatible Markdown in `/knowledge-base/`.
- **Photo Pipeline**: Field photos must flow into structured job records with proof-of-work capability.

## Phase 1 Priorities (Deadline: June 10)

- Knowledge base populated with initial field logs and operational data.
- Supabase photo-upload integration (Proof of Work engine).
- Daily AI OS habit established (this file + relevant wiki pages loaded at start of every session).

## Session Protocol (Mandatory)

At the beginning of every session with Claude or Grok, use this command: