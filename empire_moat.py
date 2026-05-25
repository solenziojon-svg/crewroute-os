"""
empire_moat.py — Empire Moat Analysis (Empire Standard v2)
───────────────────────────────────────────────────────────
Reads the empire_nexus table and surfaces which Magic Layer modules
are accumulating the most operational heat from live field data.

"Moat" = the gap between what the curriculum teaches and what
production is actually generating. High heat on a module = the
curriculum is falling behind real operations. That gap IS the moat.

WEEKLY SUNDAY WORKFLOW (after Magic Layer content agent runs):
    python empire_moat.py --trigger-diff --min-score 8
    python curriculum_vc_agent.py --pending
    # Review suggestions → approve → module updated

This version uses the Empire OS structured logging standard.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from collections import Counter
from datetime import datetime, timedelta
from typing import Optional

from empire_logging import get_logger, bind_context

logger = get_logger("empire.moat")

# ── Safe import ───────────────────────────────────────────────
try:
    from cjs_operating_hub import EmpireHub
except ImportError:
    logger.error("cjs_operating_hub.py not found — add it to the repo root")
    sys.exit(1)


# ════════════════════════════════════════════════════════════════
# CORE ANALYSIS
# ════════════════════════════════════════════════════════════════

def analyze_moat(
    min_score:   int           = 7,
    source_type: Optional[str] = None,
    days_back:   int           = 30,
    verbose:     bool          = False,
) -> dict:
    hub_path = os.getenv("HUB_DB_PATH", "cjs_operating_hub.db")

    bind_context(min_score=min_score, source_type=source_type or "all", days_back=days_back)

    if not os.path.exists(hub_path):
        logger.warning("hub_not_found", path=hub_path)
        return {"status": "no_hub", "total_pending": 0}

    try:
        with EmpireHub(hub_path) as hub:
            all_pending = hub.pending_nexus_links(min_score=min_score, limit=200)
    except Exception as e:
        logger.error("hub_query_failed", error=str(e))
        return {"status": "error", "error": str(e), "total_pending": 0}

    if source_type:
        all_pending = [p for p in all_pending if p.get("source_type") == source_type]

    if days_back and days_back < 365:
        cutoff = (datetime.utcnow() - timedelta(days=days_back)).date().isoformat()
        all_pending = [p for p in all_pending if (p.get("created_at") or "")[:10] >= cutoff]

    pending = [p for p in all_pending if p.get("target_type") == "MagicLayer_Module"]

    if not pending:
        logger.info("moat_stable", message="No pending signals above threshold")
        return {"status": "stable", "total_pending": 0}

    module_heat    = Counter(p["target_id"] for p in pending)
    source_counter = Counter(p["source_type"] for p in all_pending)

    score_map = {}
    for p in pending:
        score_map.setdefault(p["target_id"], []).append(p["insight_score"])

    hot_modules = [
        m for m, scores in score_map.items()
        if scores and (sum(scores) / len(scores)) >= 8
    ]

    note_len  = 200 if verbose else 100
    top_notes = [p["notes"][:note_len] for p in pending if p.get("notes")][:5]

    result = {
        "status":           "heat_detected",
        "total_pending":    len(pending),
        "module_heat":      dict(module_heat.most_common()),
        "source_breakdown": dict(source_counter.most_common()),
        "top_notes":        top_notes,
        "hot_modules":      hot_modules,
        "avg_score":        round(sum(p["insight_score"] for p in pending) / len(pending), 1),
    }

    _print_report(result)
    return result


def _print_report(result: dict) -> None:
    logger.info("moat_analysis_complete", total_pending=result["total_pending"], avg_score=result["avg_score"])

    for module, count in result["module_heat"].items():
        label = module.replace("magic-layer-module-", "M").replace(".md", "")
        bar   = "█" * count + "░" * max(0, 5 - count)
        hot   = " 🔥" if module in result.get("hot_modules", []) else ""
        logger.info("module_heat", module=label, count=count, hot=hot, bar=bar)

    if result["source_breakdown"]:
        for source, count in result["source_breakdown"].items():
            logger.info("signal_source", source=source, count=count)

    if result["top_notes"]:
        for note in result["top_notes"]:
            logger.info("top_field_insight", note=note[:120])

    if result["hot_modules"]:
        for m in result["hot_modules"]:
            logger.warning("hot_module_detected", module=m)
    else:
        logger.info("no_critical_modules")


# ════════════════════════════════════════════════════════════════
# CURRICULUM DIFF TRIGGER
# ════════════════════════════════════════════════════════════════

async def trigger_diff_for_hot_modules(hot_modules: list[str]) -> None:
    if not hot_modules:
        logger.info("no_hot_modules_to_diff")
        return

    try:
        from curriculum_vc_agent import CurriculumVCAgent
    except ImportError:
        logger.warning("curriculum_vc_agent_not_found")
        return

    agent = CurriculumVCAgent()
    logger.info("triggering_curriculum_diff", count=len(hot_modules))

    for module in hot_modules:
        try:
            updates = await asyncio.wait_for(agent.diff_module(module), timeout=60.0)
            if updates:
                logger.info("diff_suggestions_saved", module=module, count=len(updates))
            else:
                logger.info("no_high_confidence_suggestions", module=module)
        except Exception as e:
            logger.error("diff_failed", module=module, error=str(e))


# ════════════════════════════════════════════════════════════════
# CLI
# ════════════════════════════════════════════════════════════════

async def main():
    parser = argparse.ArgumentParser(description="Empire Moat Analysis")
    parser.add_argument("--min-score",    type=int, default=7)
    parser.add_argument("--source",       default=None)
    parser.add_argument("--days-back",    type=int, default=30)
    parser.add_argument("--trigger-diff", action="store_true")
    parser.add_argument("--verbose",      action="store_true")
    args = parser.parse_args()

    result = analyze_moat(
        min_score   = args.min_score,
        source_type = args.source,
        days_back   = args.days_back,
        verbose     = args.verbose,
    )

    if args.trigger_diff and result.get("hot_modules"):
        await trigger_diff_for_hot_modules(result["hot_modules"])
    elif args.trigger_diff:
        logger.info("no_hot_modules_found_for_diff")


if __name__ == "__main__":
    asyncio.run(main())