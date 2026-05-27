# CrewRoute AI OS — Behavioral System Rules

This file governs all LLM reasoning, code generation, and file-editing behaviors for CrewRoute OS. Load this file before initiating any session.

## The 4 Karpathy Principles of AI Orchestration

1. **Think Before Coding**  
   State assumptions explicitly. Surface confusion or missing information. Present multiple interpretations when ambiguous. Push back if a simpler approach exists.

2. **Simplicity First**  
   Deliver the minimal solution that meets the stated goal. No unrequested features, abstractions, or speculative flexibility. Prefer clean, readable code.

3. **Surgical Changes**  
   Touch only the code directly required by the current request. Match existing style and patterns. Remove only code made unused by your change.

4. **Goal-Driven Execution**  
   Convert requests into clear, verifiable success criteria. Enable autonomous looping toward measurable outcomes rather than step-by-step instructions.

## Domain-Specific Guardrails

### Pricing Model Integrity (v0.3)
Strictly enforce the following formulas:
- **Base Hours** = lawn/hardscape square footage ÷ 1,600
- **Base Cost** = Base Hours × $65.00 (standard labor rate)
- **Total Contract Price** = Base Cost ÷ (1 - 0.35) → enforces 35% target margin

### SaaS Architecture Boundaries
- **CrewRoute (Entry-Level / Commercial)**: Target 1–5 truck operations.  
  Solo tier = $79/mo, Crew tier = $149/mo. No per-user licensing. Includes HVAC flat-rate pricebook. QuickBooks Online sync in active development.
- **CrewRoute Pro (Professional)**: Designed for multi-truck operations. Includes Office Control Panel (drag-and-drop dispatch), iPad-optimized Truck Portal with live job timers, photo proof of completion, employee PTO self-service, and QuickBooks-ready CSV exports.
- **Landscape Friend (Custom/Internal SaaS)**: Built on Vercel + Next.js SSR, Neon serverless PostgreSQL, Clerk authentication, Resend for invoicing, Vercel Blobs for storage, and Google Maps API for route optimization and spatial geocoding.

### CJS Operational Rules
- Maintain phone-first workflows (photo capture → instant estimate → job logging).
- Respect asset hierarchy: Properties → Routes/Crews → Equipment/Tasks.
- All routing and scheduling logic must support measurable improvements in jobs per day and drive time reduction.
- Future government/VA contract work requires strong auditability, GPS tracking, and compliance logging.

## Active Directives

- If the user says **"Ingest [file]"** or drops new material into `raw-resources/`: Run the Bootstrap Protocol (`knowledge-base/bootstrap-prompt.txt`).
- If the user asks for code: Ensure full compatibility with modern JavaScript/TypeScript standards unless legacy CommonJS is explicitly required.
- If the user asks for a wiki update: Make edits surgically, preserve existing `[[wiki/page-name]]` cross-references, and update `knowledge-base/schema.md`.
- Before ending any session: Document what was built, update relevant wiki pages if needed, and log session notes in `knowledge-base/raw-resources/chat-exports/`.

## Context Loading Instruction

At the start of every session, the following instruction must be used:

"Load `crewroute-claude.md` from the root and read the relevant pages from `knowledge-base/wiki/` before we begin. Follow all behavioral rules and pricing formulas strictly."