"""
solo_pilot_agent.py — Sprint 1: Voice-to-Action (Empire Standard v2)
─────────────────────────────────────────────────────────────────────
Parses field voice notes / text notes and generates structured outputs:
- Client-facing message
- Upsell detection
- Job updates for EmpireHub

This version uses the Empire OS structured logging standard.

Works together with PhotoAuditAgent via process_job_completion().
"""

from __future__ import annotations

import asyncio
import json
import os
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional

from empire_logging import get_logger, bind_context

logger = get_logger("crewroute.solo_pilot")

# ════════════════════════════════════════════════════════════════
# RESULT
# ════════════════════════════════════════════════════════════════

@dataclass
class SoloPilotResult:
    success:        bool
    job_id:         str
    client_message: str
    upsell_prompt:  str
    intent:         str
    model_used:     str   = ""
    cost_usd:       float = 0.0
    duration_ms:    int   = 0
    error:          str   = ""
    created_at:     str   = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> dict:
        return asdict(self)


# ════════════════════════════════════════════════════════════════
# PROMPTS
# ════════════════════════════════════════════════════════════════

PARSE_PROMPT = """
You are parsing a landscaping field note from a solo operator.

Job ID: {job_id}
Client: {client_name}
Date: {date}

Field note / transcript:
"{transcript}"

Extract and return ONLY valid JSON:
{{
  "intent": "Short summary of what was done or observed",
  "client_message": "Professional 1-2 sentence message ready to send to the client",
  "upsell_detected": true | false,
  "upsell_prompt": "Specific upsell suggestion if detected, otherwise empty string"
}}
""".strip()


# ════════════════════════════════════════════════════════════════
# SOLO PILOT AGENT
# ════════════════════════════════════════════════════════════════

class SoloPilotAgent:
    def __init__(
        self,
        hub_path:          str = "cjs_operating_hub.db",
        anthropic_api_key: Optional[str] = None,
        operator_name:     str = "Jon",
    ):
        self.hub_path = hub_path
        self._ak = anthropic_api_key or os.getenv("ANTHROPIC_API_KEY", "")
        self.operator_name = operator_name

    async def process_voice_note(
        self,
        transcript:   str,
        job_id:       str,
        client_name:  str = "Client",
        job_type:     str = "Maintenance",
        crew:         str = "Solo",
        date:         Optional[str] = None,
        dry_run:      bool = False,
    ) -> SoloPilotResult:
        t0   = time.monotonic()
        date = date or datetime.utcnow().strftime("%Y-%m-%d")

        bind_context(job_id=job_id, client_name=client_name, dry_run=dry_run)

        if not transcript or not transcript.strip():
            return self._error_result(job_id, "Empty transcript")

        # ── Parse with Claude ─────────────────────────────────
        parsed = None
        model_used = ""
        cost_usd = 0.0

        try:
            parsed, model_used, cost_usd = await asyncio.wait_for(
                self._parse_with_claude(transcript, job_id, client_name, date),
                timeout=20.0,
            )
        except asyncio.TimeoutError:
            logger.warning("parse_timeout", using="fallback")
        except Exception as e:
            logger.warning("parse_failed", error=str(e), using="fallback")

        if parsed is None:
            parsed = self._fallback_parse(transcript)

        client_message = parsed.get("client_message", transcript[:200])
        upsell_prompt  = parsed.get("upsell_prompt", "")
        intent         = parsed.get("intent", transcript[:100])

        duration_ms = int((time.monotonic() - t0) * 1000)

        result = SoloPilotResult(
            success        = True,
            job_id         = job_id,
            client_message = client_message,
            upsell_prompt  = upsell_prompt,
            intent         = intent,
            model_used     = model_used,
            cost_usd       = cost_usd,
            duration_ms    = duration_ms,
        )

        if not dry_run:
            self._persist_to_hub(result, crew, date)

        logger.info(
            "voice_note_processed",
            job_id=job_id,
            has_upsell=bool(upsell_prompt),
            duration_ms=duration_ms,
        )
        return result

    # ── Parsing ───────────────────────────────────────────────

    async def _parse_with_claude(
        self, transcript: str, job_id: str, client_name: str, date: str
    ) -> tuple[dict, str, float]:
        import anthropic
        client = anthropic.AsyncAnthropic(api_key=self._ak)

        prompt = PARSE_PROMPT.format(
            job_id=job_id,
            client_name=client_name,
            date=date,
            transcript=transcript,
        )

        msg = await client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}],
        )

        text = msg.content[0].text.strip()
        clean = text.lstrip("```json").lstrip("```").rstrip("```").strip()
        data = json.loads(clean)

        in_tok = msg.usage.input_tokens
        out_tok = msg.usage.output_tokens
        cost = (in_tok / 1_000_000 * 0.80) + (out_tok / 1_000_000 * 4.00)
        return data, "claude-haiku-4-5", round(cost, 6)

    def _fallback_parse(self, transcript: str) -> dict:
        """Simple fallback when Claude is unavailable."""
        return {
            "intent": transcript[:120],
            "client_message": f"Job update: {transcript[:180]}",
            "upsell_detected": False,
            "upsell_prompt": "",
        }

    # ── Persistence ───────────────────────────────────────────

    def _persist_to_hub(self, result: SoloPilotResult, crew: str, date: str) -> None:
        if not os.path.exists(self.hub_path):
            return
        try:
            import sqlite3
            conn = sqlite3.connect(self.hub_path, timeout=10)
            conn.execute("""
                UPDATE jobs
                SET notes = COALESCE(notes,'') || ' [VOICE: ' || ? || ']',
                    crew = ?
                WHERE id = ? AND date = ?
            """, (result.intent[:300], crew, result.job_id, date))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.warning("hub_persist_failed", error=str(e))

    # ── Error ─────────────────────────────────────────────────

    def _error_result(self, job_id: str, error: str) -> SoloPilotResult:
        return SoloPilotResult(
            success=False,
            job_id=job_id,
            client_message="",
            upsell_prompt="",
            intent="",
            error=error,
        )


# ════════════════════════════════════════════════════════════════
# QUICK TEST
# ════════════════════════════════════════════════════════════════

async def _test():
    agent = SoloPilotAgent()
    logger.info("solo_pilot_test_started")

    result = await agent.process_voice_note(
        transcript="Finished lawn, edging done, noticed weeds in the back flowerbed.",
        job_id="TEST-001",
        client_name="Smith Residence",
        dry_run=True,
    )

    logger.info(
        "solo_pilot_test_complete",
        client_message=result.client_message[:80],
        has_upsell=bool(result.upsell_prompt),
    )


if __name__ == "__main__":
    asyncio.run(_test())