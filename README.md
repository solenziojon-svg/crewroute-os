# CrewRoute OS

The complete operating system for serious landscaping operators. Built and battle-tested at CJS Landscape Solutions.

CrewRoute OS combines field operations tooling with a powerful **AI-native development and knowledge system**, enabling faster iteration, better pricing accuracy, and scalable dispatch logic.

## CrewRoute AI OS (New)

This repository includes the full **CrewRoute AI OS** — a self-improving operating system for CrewRoute development and operations.

- **Behavioral Rules**: `crewroute-claude.md` (must be loaded at the start of every session)
- **Knowledge Base**: `knowledge-base/` — 3-layer compiled knowledge system (Raw → Wiki → Schema)
- **Quick Start**: See `knowledge-base/README.md`

### How to Use the AI OS
At the beginning of any session, tell your AI:

> "Load `crewroute-claude.md` from the root and read the relevant pages from `knowledge-base/wiki/` before we begin."

## Current Status

- **Dashboard UI**: Complete
- **Photo Analysis**: Backend connected
- **Supabase**: Connected
- **LTV / CAC / AOV Calculator**: Working
- **AI OS Layer**: Implemented (behavioral rules + knowledge base)

## Tech Stack

- Frontend: React / Next.js
- Backend: Python + Supabase
- AI Layer: Custom CrewRoute AI OS (Claude + structured knowledge base)
- Routing & Optimization: Google Maps API integration (in progress)

## Next Steps

1. Test real photo upload + analysis flow
2. Connect production Claude Vision API
3. Save job data and estimates to Supabase
4. Begin testing dynamic routing logic with AI OS

## Repository Structure