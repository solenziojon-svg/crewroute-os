"""
focus_mode_agent.py  — Sprint 3: Focus Mode Shield (Empire Standard v2)
────────────────────────────────────────────────────────────────────────
Intercepts incoming client messages while the operator is on the mower.
Classifies urgency, generates smart auto-replies, queues non-urgent
messages, and surfaces only true emergencies immediately.

The "Context Switch Tax" this eliminates:
  Every time the operator checks their phone mid-job, CJS loses 8-12 minutes
  of productive time. At $85/hr across 5 interruptions/day that's
  $1,500-2,100/month per crew in recoverable capacity.

Classification tiers:
  URGENT    → Property damage, flooding, safety. Alert fires immediately.
  CALLBACK  → Complaint or upset client. Flagged for personal response.
  REQUEST   → Quote, schedule, add-on. Auto-acknowledged with ETA.
  QUESTION  → General info, hours, pricing. Auto-answered if possible.
  PAYMENT   → Invoice, billing. Auto-acknowledged.
  SOCIAL    → "Thanks!", "Great job". Logged, no reply needed.

This version uses the Empire OS structured logging standard (empire_logging.py).

Usage:
    from focus_mode_agent import FocusModeAgent

    agent = FocusModeAgent()
    result = await agent.process_incoming(
        message     = "Hi, the sprinklers are flooding my driveway!",
        client_name = "Smith Residence",
        dry_run     = True,
    )
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

logger = get_logger("crewroute.focus_mode")

# ── Urgency tiers ─────────────────────────────────────────────
TIER_URGENT   = "URGENT"
TIER_CALLBACK = "CALLBACK"
TIER_REQUEST  = "REQUEST"
TIER_QUESTION = "QUESTION"
TIER_PAYMENT  = "PAYMENT"
TIER_SOCIAL   = "SOCIAL"

TIER_PRIORITY = {
    TIER_URGENT: 0, TIER_CALLBACK: 1, TIER_REQUEST: 2,
    TIER_QUESTION: 3, TIER_PAYMENT: 4, TIER_SOCIAL: 5,
}


# ════════════════════════════════════════════════════════════════
# PROMPTS
# ════════════════════════════════════════════════════════════════

CLASSIFY_PROMPT = """
You are the Focus Mode Shield for a solo landscaping operator.
Your job is to classify incoming client messages so the operator
can stay focused on physical work without unnecessary interruptions.

Operator: {operator_name}
Business: {business_name}
Client: {client_name}
Message: "{message}"
Time received: {time_received}

Classify this message into exactly one tier:
  URGENT    = Immediate safety or property risk (flooding, damage, fire, injury)
  CALLBACK  = Complaint, upset client, or service dispute — needs personal reply
  REQUEST   = Quote request, reschedule, add-on service, new job
  QUESTION  = General question about hours, pricing, services, timing
  PAYMENT   = Invoice, payment, billing inquiry
  SOCIAL    = Thank you, compliment, casual chat — no action needed

Return ONLY valid JSON:
{{
  "tier": "URGENT|CALLBACK|REQUEST|QUESTION|PAYMENT|SOCIAL",
  "confidence": 0.0-1.0,
  "intent_summary": "One sentence: what the client actually wants",
  "urgency_reason": "Why this is urgent, or empty string if not urgent",
  "suggested_eta": "When operator can realistically respond e.g. 'by 5 PM today'"
}}
""".strip()

REPLY_PROMPT = """
You are writing an SMS auto-reply on behalf of {operator_name} at {business_name}.
The operator is currently in the field completing landscaping work.

Client: {client_name}
Their message: "{message}"
Message tier: {tier}
Intent: {intent_summary}
Suggested ETA: {suggested_eta}

Write a short, professional SMS auto-reply (2-3 sentences max).

Rules by tier:
  REQUEST  → Acknowledge the request, give a specific response time, confirm you'll follow up
  QUESTION → Answer the question if you can from context, or give ETA for full answer
  PAYMENT  → Acknowledge, confirm you'll review and respond by ETA
  SOCIAL   → Warm, brief thank-you (1 sentence only)

NEVER use corporate filler. Always end with the operator's first name only.
Return ONLY the reply text. No labels, no quotes.
""".strip()


# ════════════════════════════════════════════════════════════════
# RESULT
# ════════════════════════════════════════════════════════════════

@dataclass
class FocusModeResult:
    success:        bool
    message_id:     str
    client_name:    str
    tier:           str
    confidence:     float
    intent_summary: str
    auto_reply:     str
    alert_fired:    bool
    needs_followup: bool
    queue_position: Optional[int]
    suggested_eta:  str
    model_used:     str   = ""
    cost_usd:       float = 0.0
    duration_ms:    int   = 0
    error:          str   = ""
    created_at:     str   = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> dict:
        return asdict(self)

    def operator_summary(self) -> str:
        icon = {"URGENT":"🚨","CALLBACK":"⚠️","REQUEST":"📋",
                "QUESTION":"❓","PAYMENT":"💰","SOCIAL":"👍"}.get(self.tier, "•")
        return f"{icon} {self.tier} — {self.client_name}: {self.intent_summary[:60]}"


# ════════════════════════════════════════════════════════════════
# FOCUS MODE AGENT
# ════════════════════════════════════════════════════════════════

class FocusModeAgent:
    def __init__(
        self,
        hub_path:          str = "cjs_operating_hub.db",
        anthropic_api_key: Optional[str] = None,
        operator_name:     str = "Jon",
        business_name:     str = "CJS Landscape Solutions",
    ):
        self.hub_path      = hub_path
        self._ak           = anthropic_api_key or os.getenv("ANTHROPIC_API_KEY", "")
        self.operator_name = operator_name
        self.business_name = business_name

    async def process_incoming(
        self,
        message:      str,
        client_name:  str = "Client",
        client_phone: str = "",
        job_id:       str = "",
        dry_run:      bool = False,
    ) -> FocusModeResult:
        t0         = time.monotonic()
        message_id = f"msg-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}"

        bind_context(
            message_id=message_id,
            client_name=client_name,
            job_id=job_id or "none",
            dry_run=dry_run,
        )

        if not message or not message.strip():
            return self._error_result(message_id, client_name, "Empty message")

        # ── Classify ──────────────────────────────────────────
        classification = None
        model_used     = ""
        cost_usd       = 0.0

        try:
            classification, model_used, cost_usd = await asyncio.wait_for(
                self._classify(message, client_name),
                timeout=15.0,
            )
        except asyncio.TimeoutError:
            logger.warning("classify_timeout", fallback="keyword")
        except Exception as e:
            logger.warning("classify_failed", error=str(e), fallback="keyword")

        if classification is None:
            classification = self._keyword_classify(message)

        tier           = classification.get("tier", TIER_QUESTION)
        confidence     = float(classification.get("confidence", 0.7))
        intent_summary = classification.get("intent_summary", message[:60])
        urgency_reason = classification.get("urgency_reason", "")
        suggested_eta  = classification.get("suggested_eta", "by end of day")

        logger.info(
            "message_classified",
            tier=tier,
            confidence=round(confidence, 2),
            intent=intent_summary[:80],
        )

        alert_fired    = False
        needs_followup = False
        auto_reply     = ""
        queue_position = None

        if tier == TIER_URGENT:
            needs_followup = True
            if not dry_run:
                await self._fire_urgent_alert(client_name, message, urgency_reason, message_id)
                alert_fired = True
            logger.warning("urgent_alert_fired", client=client_name, reason=urgency_reason[:80])

        elif tier == TIER_CALLBACK:
            needs_followup = True
            queue_position = self._persist_message(
                message_id, client_name, client_phone,
                message, tier, intent_summary, suggested_eta,
                job_id, dry_run,
            )
            logger.warning("callback_queued", client=client_name, position=queue_position)

        else:
            try:
                auto_reply = await asyncio.wait_for(
                    self._generate_reply(message, client_name, tier, intent_summary, suggested_eta),
                    timeout=15.0,
                )
                cost_usd += 0.0001
            except Exception as e:
                logger.warning("reply_generation_failed", error=str(e), using="template")
                auto_reply = self._template_reply(client_name, tier, suggested_eta)

            queue_position = self._persist_message(
                message_id, client_name, client_phone,
                message, tier, intent_summary, suggested_eta,
                job_id, dry_run, auto_reply=auto_reply,
            )

        duration_ms = int((time.monotonic() - t0) * 1000)

        result = FocusModeResult(
            success        = True,
            message_id     = message_id,
            client_name    = client_name,
            tier           = tier,
            confidence     = confidence,
            intent_summary = intent_summary,
            auto_reply     = auto_reply,
            alert_fired    = alert_fired,
            needs_followup = needs_followup,
            queue_position = queue_position,
            suggested_eta  = suggested_eta,
            model_used     = model_used,
            cost_usd       = cost_usd,
            duration_ms    = duration_ms,
        )

        logger.info(
            "focus_mode_complete",
            summary=result.operator_summary(),
            has_reply=bool(auto_reply),
            alert_fired=alert_fired,
            duration_ms=duration_ms,
        )
        return result

    # ── Classification ────────────────────────────────────────

    async def _classify(self, message: str, client_name: str) -> tuple[dict, str, float]:
        prompt = CLASSIFY_PROMPT.format(
            operator_name = self.operator_name,
            business_name = self.business_name,
            client_name   = client_name,
            message       = message,
            time_received = datetime.now().strftime("%I:%M %p"),
        )
        text, model, cost = await self._claude(prompt, max_tokens=200)
        clean = text.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
        data  = json.loads(clean)
        return data, model, cost

    def _keyword_classify(self, message: str) -> dict:
        text = message.lower()
        urgent_kw  = ["flood","flooding","leak","broken pipe","damage","fire","emergency","urgent","injury","hurt","dangerous","overflow"]
        callback_kw = ["disappointed","terrible","unacceptable","complaint","not happy","refund","never again","lawsuit","bad job"]
        payment_kw  = ["invoice","payment","bill","charge","receipt","owe","paid"]
        request_kw  = ["quote","estimate","schedule","book","add","also","can you","could you","would you","need","want"]

        if any(k in text for k in urgent_kw):
            tier = TIER_URGENT
            reason = next((k for k in urgent_kw if k in text), "urgency keyword")
        elif any(k in text for k in callback_kw):
            tier = TIER_CALLBACK
            reason = ""
        elif any(k in text for k in payment_kw):
            tier = TIER_PAYMENT
            reason = ""
        elif any(k in text for k in request_kw):
            tier = TIER_REQUEST
            reason = ""
        elif "?" in message:
            tier = TIER_QUESTION
            reason = ""
        else:
            tier = TIER_SOCIAL
            reason = ""

        return {
            "tier": tier,
            "confidence": 0.65,
            "intent_summary": message[:60],
            "urgency_reason": reason,
            "suggested_eta": "by 5 PM today",
        }

    # ── Reply generation ──────────────────────────────────────

    async def _generate_reply(self, message: str, client_name: str, tier: str, intent_summary: str, suggested_eta: str) -> str:
        prompt = REPLY_PROMPT.format(
            operator_name  = self.operator_name,
            business_name  = self.business_name,
            client_name    = client_name,
            message        = message,
            tier           = tier,
            intent_summary = intent_summary,
            suggested_eta  = suggested_eta,
        )
        text, _, _ = await self._claude(prompt, max_tokens=150)
        return text.strip()

    def _template_reply(self, client_name: str, tier: str, eta: str) -> str:
        name = client_name.split()[0] if client_name else "there"
        templates = {
            TIER_REQUEST:  f"Hi {name}, got your message. I'm in the field right now and will follow up {eta}. — {self.operator_name}",
            TIER_QUESTION: f"Hi {name}, thanks for reaching out. I'll get back to you {eta} with a full answer. — {self.operator_name}",
            TIER_PAYMENT:  f"Hi {name}, received your message about billing. I'll review and respond {eta}. — {self.operator_name}",
            TIER_SOCIAL:   f"Thank you! — {self.operator_name}",
        }
        return templates.get(tier, f"Hi {name}, got your message — will follow up {eta}. — {self.operator_name}")

    # ── Alert ─────────────────────────────────────────────────

    async def _fire_urgent_alert(self, client_name: str, message: str, reason: str, message_id: str) -> None:
        try:
            from alerts import dispatch_alert
            await dispatch_alert(
                title  = f"🚨 URGENT — {client_name}",
                body   = f"{message[:120]}\nReason: {reason[:60]}",
                status = "red",
            )
        except ImportError:
            logger.warning("alerts_module_not_found", action="urgent_alert_skipped")
        except Exception as e:
            logger.error("urgent_alert_failed", error=str(e))

    # ── Hub persistence ───────────────────────────────────────

    def _persist_message(self, message_id, client_name, client_phone, message, tier, intent, eta, job_id, dry_run, auto_reply=""):
        if dry_run or not os.path.exists(self.hub_path):
            return None
        try:
            import sqlite3
            conn = sqlite3.connect(self.hub_path, timeout=10)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS message_queue (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    message_id TEXT UNIQUE,
                    client_name TEXT,
                    client_phone TEXT,
                    message TEXT,
                    tier TEXT,
                    intent TEXT,
                    auto_reply TEXT,
                    suggested_eta TEXT,
                    job_id TEXT,
                    needs_followup INTEGER DEFAULT 0,
                    replied INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT (datetime('now'))
                )
            """)
            conn.execute("""
                INSERT OR IGNORE INTO message_queue
                (message_id, client_name, client_phone, message, tier, intent, auto_reply, suggested_eta, job_id, needs_followup)
                VALUES (?,?,?,?,?,?,?,?,?,?)
            """, (message_id, client_name, client_phone, message[:500], tier, intent[:200], auto_reply, eta, job_id, 1 if tier == TIER_CALLBACK else 0))
            pos = conn.execute("SELECT COUNT(*) FROM message_queue WHERE replied=0").fetchone()[0]
            conn.commit()
            conn.close()
            return pos
        except Exception as e:
            logger.warning("queue_persist_failed", error=str(e))
            return None

    # ── Claude call ───────────────────────────────────────────

    async def _claude(self, prompt: str, max_tokens: int = 200) -> tuple[str, str, float]:
        import anthropic
        client = anthropic.AsyncAnthropic(api_key=self._ak)
        msg = await client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        text = msg.content[0].text
        in_tok = msg.usage.input_tokens
        out_tok = msg.usage.output_tokens
        cost = (in_tok / 1_000_000 * 0.80) + (out_tok / 1_000_000 * 4.00)
        return text, "claude-haiku-4-5", round(cost, 6)

    def _error_result(self, message_id: str, client_name: str, error: str) -> FocusModeResult:
        return FocusModeResult(
            success=False, message_id=message_id, client_name=client_name,
            tier=TIER_QUESTION, confidence=0.0, intent_summary="",
            auto_reply="", alert_fired=False, needs_followup=False,
            queue_position=None, suggested_eta="", error=error,
        )


# ════════════════════════════════════════════════════════════════
# QUEUE HELPERS
# ════════════════════════════════════════════════════════════════

def pending_followups(hub_path: str = "cjs_operating_hub.db") -> list[dict]:
    if not os.path.exists(hub_path):
        return []
    try:
        import sqlite3
        conn = sqlite3.connect(hub_path, timeout=10)
        conn.row_factory = sqlite3.Row
        rows = conn.execute("""
            SELECT * FROM message_queue
            WHERE replied=0
            ORDER BY CASE tier
                WHEN 'URGENT' THEN 0 WHEN 'CALLBACK' THEN 1 WHEN 'REQUEST' THEN 2
                WHEN 'QUESTION' THEN 3 WHEN 'PAYMENT' THEN 4 ELSE 5 END,
                created_at ASC
        """).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception as e:
        logger.warning("pending_followups_failed", error=str(e))
        return []


def mark_replied(message_id: str, hub_path: str = "cjs_operating_hub.db") -> bool:
    if not os.path.exists(hub_path):
        return False
    try:
        import sqlite3
        conn = sqlite3.connect(hub_path, timeout=10)
        cur = conn.execute("UPDATE message_queue SET replied=1 WHERE message_id=?", (message_id,))
        conn.commit()
        conn.close()
        return cur.rowcount > 0
    except Exception:
        return False


# ════════════════════════════════════════════════════════════════
# QUICK TEST (local only)
# ════════════════════════════════════════════════════════════════

async def _test():
    test_messages = [
        ("The sprinklers flooded my entire driveway — water everywhere!", "Smith Residence", TIER_URGENT),
        ("Can you give me a quote for monthly weed control in the backyard?", "Martinez Residence", TIER_REQUEST),
        ("What time are you coming on Thursday?", "Del Mar Beach Club", TIER_QUESTION),
        ("I'm very disappointed with the service last week.", "Mission Hills HOA", TIER_CALLBACK),
        ("Just wanted to say the yard looks amazing, thank you!", "Rancho Santa Fe Client", TIER_SOCIAL),
    ]

    agent = FocusModeAgent()
    logger.info("focus_mode_test_started")

    for message, client, expected_tier in test_messages:
        result = await agent.process_incoming(message=message, client_name=client, dry_run=True)
        match = "✅" if result.tier == expected_tier else "⚠️"
        logger.info("test_result", match=match, summary=result.operator_summary(), confidence=round(result.confidence, 2))

    logger.info("focus_mode_test_complete")


if __name__ == "__main__":
    asyncio.run(_test())