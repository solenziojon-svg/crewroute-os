# CrewRoute AI OS — Behavioral Profile & System Rules
Version: 1.1 | Paradigm: Context Engineering & Persistent Memory

## 1. Core Operating Principles (The Karpathy Method)
1. **Raw is Sacred:** Never modify files inside `/raw-resources/`. Treat them as immutable event logs.
2. **Wiki is Fluid but Dense:** The `/wiki/` directory must compress raw logs into architectural truths using highly concentrated, multi-layered markdown.
3. **Govern via Schema:** Every edit must cross-reference `schema.md` to update status logs and maintain data integrity.
4. **Auto-Research Feedback:** Every session must extract operational friction points and document them as permanent design constraints to prevent logic regressions.

## 2. Technical Stack Boundaries
- **Backend:** Supabase (PostgreSQL), Edge Functions.
- **Frontend:** Next.js (App Router), deployed on Vercel.
- **Routing Engine:** Python, Google Maps Distance Matrix API (with traffic caching), Google OR-Tools VRP Solver.
- **Database Schema Anchors:** `profiles`, `clients`, `jobs`, `job_photos`.

## 3. Financial & Domain Formulas (v0.3 Baseline)
- **Base Labor Rate:** $65.00 / hour (burdened).
- **Target Gross Margin:** 35%.
- **Estimating Equation:** Base Hours = SqFt / 1600.
- **Total Price Equation:** Price = ((Base Hours * 65) + Materials) / (1 - 0.35).
- **Material Markup Factor:** 1.54x minimum.

## 4. Geographic Constraint Mapping (San Diego Territory)
- **Zone A (Pacific Beach):** Extreme density, narrow alleys, trailers restricted. Rule: Apply a mandatory 10-minute "Parking Tax" penalty to the OR-Tools transit matrix for all PB destination nodes.
- **Zone B (North County Coastal):** Wide transit spans along I-5 corridor. Rule: Enforce cluster-density routing to eliminate non-billable windshield time.

## 5. Interaction Rules for Agents
- **No Fluff:** Do not apologize, congratulate, or use conversational filler. Lead with structural code or actionable strategy.
- **Enforce State:** If a prompt violates v0.3 pricing or database constraints, flag it immediately before generating code.
- **Obsidian Compatibility:** Always wrap cross-references in standard internal link syntax: [[wiki/page-name]].
