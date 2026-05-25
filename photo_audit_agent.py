"""
photo_audit_agent.py  — Sprint 2: Photo Auto-Auditing (Empire Standard v2)
────────────────────────────────────────────────────────────────────────────
Analyzes job completion photos using Claude Vision.
Produces quality verification, upsell detection, and a client-ready caption.

This version uses the Empire OS structured logging standard (empire_logging.py).

Flow:
  1. Accept photo (URL or base64)
  2. Claude Vision → quality check + upsell scan
  3. Generate client-ready caption
  4. Write audit record to EmpireHub
  5. Fire Make.com webhook
  6. Return PhotoAuditResult

Combined entry point:
    process_job_completion()  → runs Voice + Photo agents together
"""

from __future__ import annotations

import asyncio
import base64
import json
import os
import time
import urllib.request
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional

from empire_logging import get_logger, bind_context

logger = get_logger("crewroute.photo_audit")

# ════════════════════════════════════════════════════════════════
# RESULT
# ════════════════════════════════════════════════════════════════

@dataclass
class PhotoAuditResult:
    success:          bool
    job_id:           str
    quality_status:   str
    quality_notes:    str
    quality_score:    int
    upsell_detected:  bool
    upsell_text:      str
    upsell_service:   str
    gate_flag:        bool
    gate_note:        str
    client_caption:   str
    photo_url:        str   = ""
    model_used:       str   = ""
    cost_usd:         float = 0.0
    duration_ms:      int   = 0
    error:            str   = ""
    created_at:       str   = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> dict:
        return asdict(self)

    def to_make_payload(self) -> dict:
        return {
            "source":          "photo_audit_agent",
            "schema_version":  "1.0",
            "dispatched_at":   self.created_at + "Z",
            "job_id":          self.job_id,
            "quality_status":  self.quality_status,
            "quality_score":   self.quality_score,
            "upsell_detected": self.upsell_detected,
            "upsell_text":     self.upsell_text,
            "upsell_service":  self.upsell_service,
            "gate_flag":       self.gate_flag,
            "gate_note":       self.gate_note,
            "client_caption":  self.client_caption,
            "photo_url":       self.photo_url,
        }

    def ui_notification(self) -> str:
        parts = [f"Photo processed — {self.quality_status.replace('_',' ').title()}"]
        if self.upsell_detected:
            parts.append(f"Upsell: {self.upsell_text[:80]}")
        if self.gate_flag:
            parts.append(f"Flag: {self.gate_note[:60]}")
        parts.append("Ready to send invoice? Tap to confirm.")
        return " · ".join(parts[:2]) + "\n" + parts[-1]


# ════════════════════════════════════════════════════════════════
# PROMPTS
# ════════════════════════════════════════════════════════════════

AUDIT_PROMPT = """
You are analyzing a landscaping job completion photo for a professional operator.
Your job is to produce a structured quality audit and upsell report.

Job context:
- Job ID: {job_id}
- Client: {client_name}
- Service type: {job_type}
- Date: {date}

Analyze the photo and return ONLY valid JSON (no markdown):
{{
  "quality_status": "verified" | "issues_found" | "unclear",
  "quality_notes": "1-2 sentence description of what you see. Be specific.",
  "quality_score": integer 1-10,
  "upsell_detected": true | false,
  "upsell_text": "Specific upsell observation, or empty string.",
  "upsell_service": "Weed Control | Irrigation Service | Tree Trimming | Fertilization | Mulching | Pest Control | Overseeding | Cleanup | Repair",
  "gate_flag": true | false,
  "gate_note": "Safety, access, or damage observation if flagged.",
  "client_caption": "One professional sentence suitable for attaching to a client invoice photo."
}}

Rules:
- quality_score 8-10: professional finish, clean edges, no debris
- quality_score 5-7: acceptable but imperfect
- quality_score 1-4: visible issues that may need a callback
- Only flag upsell if you can see a specific, actionable opportunity
""".strip()


# ════════════════════════════════════════════════════════════════
# PHOTO AUDIT AGENT
# ════════════════════════════════════════════════════════════════

class PhotoAuditAgent:
    def __init__(
        self,
        hub_path:          str = "cjs_operating_hub.db",
        anthropic_api_key: Optional[str] = None,
    ):
        self.hub_path = hub_path
        self._ak = anthropic_api_key or os.getenv("ANTHROPIC_API_KEY", "")

    async def analyze(
        self,
        job_id:       str,
        photo_url:    Optional[str] = None,
        photo_base64: Optional[str] = None,
        media_type:   str = "image/jpeg",
        client_name:  str = "",
        job_type:     str = "Maintenance",
        date:         Optional[str] = None,
        dry_run:      bool = False,
    ) -> PhotoAuditResult:
        t0   = time.monotonic()
        date = date or datetime.utcnow().strftime("%Y-%m-%d")

        bind_context(job_id=job_id, client_name=client_name, dry_run=dry_run)

        if not photo_url and not photo_base64:
            return self._error_result(job_id, photo_url or "", "No photo provided")

        # ── Load image ────────────────────────────────────────
        img_b64, img_media_type = None, media_type
        if photo_base64:
            img_b64 = photo_base64
            img_media_type = media_type
        elif photo_url:
            try:
                img_b64, img_media_type = await asyncio.wait_for(
                    asyncio.get_running_loop().run_in_executor(
                        None, self._fetch_image_as_base64, photo_url
                    ),
                    timeout=15.0,
                )
            except Exception as e:
                logger.warning("image_fetch_failed", error=str(e))
                return self._error_result(job_id, photo_url, f"Image fetch failed: {e}")

        # ── Claude Vision call ────────────────────────────────
        audit_data = None
        model_used = ""
        cost_usd   = 0.0

        try:
            audit_data, model_used, cost_usd = await asyncio.wait_for(
                self._run_vision(img_b64, img_media_type, job_id, client_name, job_type, date),
                timeout=30.0,
            )
        except asyncio.TimeoutError:
            logger.warning("vision_timeout", using="safe_default")
        except Exception as e:
            logger.warning("vision_failed", error=str(e), using="safe_default")

        if audit_data is None:
            audit_data = {
                "quality_status": "unclear",
                "quality_notes":  "Unable to process photo automatically. Manual review needed.",
                "quality_score":  5,
                "upsell_detected": False,
                "upsell_text":    "",
                "upsell_service": "",
                "gate_flag":      False,
                "gate_note":      "",
                "client_caption": f"{job_type} service completed — {date}.",
            }

        duration_ms = int((time.monotonic() - t0) * 1000)

        result = PhotoAuditResult(
            success         = True,
            job_id          = job_id,
            quality_status  = audit_data.get("quality_status", "unclear"),
            quality_notes   = audit_data.get("quality_notes", ""),
            quality_score   = int(audit_data.get("quality_score", 5)),
            upsell_detected = bool(audit_data.get("upsell_detected", False)),
            upsell_text     = audit_data.get("upsell_text", ""),
            upsell_service  = audit_data.get("upsell_service", ""),
            gate_flag       = bool(audit_data.get("gate_flag", False)),
            gate_note       = audit_data.get("gate_note", ""),
            client_caption  = audit_data.get("client_caption", ""),
            photo_url       = photo_url or "",
            model_used      = model_used,
            cost_usd        = cost_usd,
            duration_ms     = duration_ms,
        )

        if not dry_run:
            self._persist(result, date)
            await self._fire_webhook(result)

        logger.info(
            "photo_audit_complete",
            job_id=job_id,
            quality=result.quality_status,
            score=result.quality_score,
            upsell=result.upsell_detected,
            flag=result.gate_flag,
            cost_usd=round(cost_usd, 5),
            duration_ms=duration_ms,
        )
        return result

    # ── Vision call ───────────────────────────────────────────

    async def _run_vision(
        self, img_b64: str, media_type: str, job_id: str,
        client_name: str, job_type: str, date: str,
    ) -> tuple[dict, str, float]:
        import anthropic
        client = anthropic.AsyncAnthropic(api_key=self._ak)

        prompt = AUDIT_PROMPT.format(
            job_id=job_id,
            client_name=client_name or "Client",
            job_type=job_type,
            date=date,
        )

        msg = await client.messages.create(
            model      = "claude-haiku-4-5-20251001",
            max_tokens = 500,
            messages   = [{
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type":       "base64",
                            "media_type": media_type,
                            "data":       img_b64,
                        },
                    },
                    {"type": "text", "text": prompt},
                ],
            }],
        )

        text  = msg.content[0].text.strip()
        clean = text.lstrip("```json").lstrip("```").rstrip("```").strip()
        data  = json.loads(clean)

        in_tok  = msg.usage.input_tokens
        out_tok = msg.usage.output_tokens
        cost = (in_tok / 1_000_000 * 0.80) + (out_tok / 1_000_000 * 4.00)
        return data, "claude-haiku-4-5-vision", round(cost, 6)

    # ── Image loading ─────────────────────────────────────────

    def _fetch_image_as_base64(self, url: str) -> tuple[str, str]:
        req = urllib.request.Request(url, headers={"User-Agent": "CrewRoute-OS/1.0"})
        with urllib.request.urlopen(req, timeout=12) as resp:
            raw = resp.read()
            media_type = resp.headers.get("Content-Type", "image/jpeg").split(";")[0].strip()
            media_type = {
                "image/jpg": "image/jpeg",
                "image/png": "image/png",
                "image/webp": "image/webp",
            }.get(media_type, "image/jpeg")
            return base64.b64encode(raw).decode("utf-8"), media_type

    # ── Hub persistence ───────────────────────────────────────

    def _persist(self, result: PhotoAuditResult, date: str) -> None:
        if not os.path.exists(self.hub_path):
            return
        try:
            import sqlite3
            conn = sqlite3.connect(self.hub_path, timeout=10)

            note_parts = [
                f"Quality: {result.quality_status} ({result.quality_score}/10)",
                result.quality_notes[:100] if result.quality_notes else "",
                f"Upsell: {result.upsell_text}" if result.upsell_detected else "",
                f"Flag: {result.gate_note}" if result.gate_flag else "",
            ]
            audit_note = " | ".join(p for p in note_parts if p)

            conn.execute("""
                UPDATE jobs
                SET photo_url=?,
                    notes=COALESCE(notes,'') || ' [PHOTO: ' || ? || ']'
                WHERE id=? AND date=?
            """, (result.photo_url, audit_note[:300], result.job_id, date))

            conn.execute("""
                CREATE TABLE IF NOT EXISTS photo_audits (
                    id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(8)))),
                    job_id TEXT, date TEXT, photo_url TEXT,
                    quality_status TEXT, quality_score INTEGER,
                    upsell_detected INTEGER DEFAULT 0, upsell_text TEXT,
                    upsell_service TEXT, gate_flag INTEGER DEFAULT 0,
                    gate_note TEXT, client_caption TEXT,
                    model_used TEXT, cost_usd REAL DEFAULT 0.0,
                    created_at TEXT DEFAULT (datetime('now'))
                )
            """)
            conn.execute("""
                INSERT INTO photo_audits
                (job_id, date, photo_url, quality_status, quality_score,
                 upsell_detected, upsell_text, upsell_service,
                 gate_flag, gate_note, client_caption, model_used, cost_usd)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                result.job_id, date, result.photo_url,
                result.quality_status, result.quality_score,
                int(result.upsell_detected), result.upsell_text, result.upsell_service,
                int(result.gate_flag), result.gate_note,
                result.client_caption, result.model_used, result.cost_usd,
            ))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.warning("hub_persist_failed", error=str(e))

    # ── Webhook ───────────────────────────────────────────────

    async def _fire_webhook(self, result: PhotoAuditResult) -> None:
        webhook_url = os.getenv("MAKE_WEBHOOK_URL", "").strip()
        if not webhook_url:
            return
        try:
            payload = json.dumps(result.to_make_payload(), default=str).encode("utf-8")
            req = urllib.request.Request(
                url=webhook_url, data=payload, method="POST",
                headers={"Content-Type": "application/json", "X-Source": "photo_audit_agent"},
            )
            loop = asyncio.get_running_loop()
            await asyncio.wait_for(
                loop.run_in_executor(None, lambda: urllib.request.urlopen(req, timeout=10)),
                timeout=12.0,
            )
        except Exception as e:
            logger.warning("webhook_failed", error=str(e))

    # ── Error result ──────────────────────────────────────────

    def _error_result(self, job_id: str, photo_url: str, error: str) -> PhotoAuditResult:
        return PhotoAuditResult(
            success=False, job_id=job_id, quality_status="unclear",
            quality_notes="", quality_score=0, upsell_detected=False,
            upsell_text="", upsell_service="", gate_flag=False,
            gate_note="", client_caption="", photo_url=photo_url, error=error,
        )


# ════════════════════════════════════════════════════════════════
# COMBINED ENTRY POINT (Voice + Photo)
# ════════════════════════════════════════════════════════════════

async def process_job_completion(
    job_id:       str,
    transcript:   str = "",
    photo_url:    Optional[str] = None,
    photo_base64: Optional[str] = None,
    client_name:  str = "",
    job_type:     str = "Maintenance",
    crew:         str = "Solo",
    date:         Optional[str] = None,
    hub_path:     str = "cjs_operating_hub.db",
    dry_run:      bool = False,
) -> dict:
    """
    Unified entry point for Voice + Photo processing.
    Runs both agents concurrently with proper error isolation.
    """
    from solo_pilot_agent import SoloPilotAgent

    t0   = time.monotonic()
    date = date or datetime.utcnow().strftime("%Y-%m-%d")

    bind_context(job_id=job_id, client_name=client_name, dry_run=dry_run)

    if not job_id or not str(job_id).strip():
        return {"success": False, "error": "job_id is required"}

    has_voice = bool(transcript and transcript.strip())
    has_photo = bool(photo_url or photo_base64)

    if not has_voice and not has_photo:
        return {"success": False, "error": "Nothing to process"}

    logger.info("process_job_completion_started", has_voice=has_voice, has_photo=has_photo)

    async def _run_voice():
        try:
            agent = SoloPilotAgent(hub_path=hub_path)
            result = await agent.process_voice_note(
                transcript=transcript, job_id=job_id, crew=crew,
                client_name=client_name, job_type=job_type, date=date, dry_run=dry_run,
            )
            return result.to_dict()
        except Exception as e:
            logger.error("voice_agent_failed", error=str(e))
            return None

    async def _run_photo():
        try:
            agent = PhotoAuditAgent(hub_path=hub_path)
            result = await agent.analyze(
                job_id=job_id, photo_url=photo_url, photo_base64=photo_base64,
                client_name=client_name, job_type=job_type, date=date, dry_run=dry_run,
            )
            return result.to_dict()
        except Exception as e:
            logger.error("photo_agent_failed", error=str(e))
            return None

    coros = []
    if has_voice: coros.append(_run_voice())
    if has_photo: coros.append(_run_photo())

    results = await asyncio.gather(*coros, return_exceptions=True)

    voice_data = results[0] if has_voice and not isinstance(results[0], Exception) else None
    photo_data = results[-1] if has_photo and not isinstance(results[-1], Exception) else None

    any_success = (voice_data is not None) or (photo_data is not None)
    if not any_success:
        return {"success": False, "error": "All agents failed"}

    # Build merged outputs
    client_message = ""
    if voice_data and voice_data.get("client_message"):
        client_message = voice_data["client_message"]
    if photo_data and photo_data.get("client_caption") and photo_data.get("quality_status") == "verified":
        client_message = f"{client_message}\n\n📸 {photo_data['client_caption']}".strip()

    upsell_prompt = ""
    if photo_data and photo_data.get("upsell_detected"):
        upsell_prompt = photo_data.get("upsell_text", "")
    elif voice_data:
        upsell_prompt = voice_data.get("upsell_prompt", "")

    flags = []
    if photo_data and photo_data.get("gate_flag"):
        flags.append(f"gate: {photo_data.get('gate_note', '')}")

    duration_ms = int((time.monotonic() - t0) * 1000)

    return {
        "success": True,
        "job_id": job_id,
        "dry_run": dry_run,
        "voice": voice_data,
        "photo": photo_data,
        "client_message": client_message,
        "upsell_prompt": upsell_prompt,
        "flags": flags,
        "duration_ms": duration_ms,
    }


# ════════════════════════════════════════════════════════════════
# QUICK TEST (local only)
# ════════════════════════════════════════════════════════════════

async def _test():
    agent = PhotoAuditAgent()
    logger.info("photo_audit_test_started")

    # Use a public sample image for testing
    test_url = "https://upload.wikimedia.org/wikipedia/commons/thumb/3/3f/Biome_grassland_LLNL.jpg/320px-Biome_grassland_LLNL.jpg"

    result = await agent.analyze(
        job_id="TEST-001",
        photo_url=test_url,
        client_name="Test Client",
        job_type="Full Maintenance",
        dry_run=True,
    )

    logger.info(
        "photo_audit_test_complete",
        quality=result.quality_status,
        score=result.quality_score,
        upsell=result.upsell_detected,
    )


if __name__ == "__main__":
    asyncio.run(_test())