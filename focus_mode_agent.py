"""
focus_mode_agent.py — Sprint 3: Focus Mode Shield
────────────────────────────────────────────────────
Intercepts incoming client messages while the operator is on the mower.
Classifies urgency, generates smart auto-replies, queues non-urgent
messages, and surfaces only true emergencies immediately.

Usage:
    agent = FocusModeAgent()
    result = await agent.process_incoming(
        message="Hi, the sprinklers are flooding my driveway!",
        client_name="Smith Residence",
        client_phone="+16195551234",
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

# ── Empire OS Integration ─────────────────────────────────────
from empire_logging import get_logger
logger = get_logger("crewroute.focus_mode")

# ── Urgency tiers ─────────────────────────────────────────────
TIER_URGENT   = "URGENT"
TIER_CALLBACK = "CALLBACK"
TIER_REQUEST  = "REQUEST"
TIER_QUESTION = "QUESTION"
TIER_PAYMENT  = "PAYMENT"
TIER_SOCIAL   = "SOCIAL"

# ════════════════════════════════════════════════════════════════
# PROMPTS
# ════════════════════════════════════════════════════════════════

CLASSIFY_PROMPT = """
You are the Focus Mode Shield for a solo landscaping operator.
Classify this message for {operator_name} at {business_name}.
Client: {client_name}
Message: "{message}"
Time received: {time_received}

Return ONLY valid JSON:
{{
  "tier": "URGENT|CALLBACK|REQUEST|QUESTION|PAYMENT|SOCIAL",
  "confidence": 0.0-1.0,
  "intent_summary": "One sentence summary",
  "urgency_reason": "Why urgent, or empty string",
  "suggested_eta": "e.g. 'by 5 PM today'"
}}
""".strip()

REPLY_PROMPT = """
Write a short, professional SMS auto-reply for {operator_name} at {business_name}.
Client: {client_name}
Message: "{message}"
Tier: {tier}
Intent: {intent_summary}
ETA: {suggested_eta}

Rules:
  - 2-3 sentences max.
  - No corporate filler or "sorry for inconvenience".
  - End with {operator_name}.
Return ONLY the reply text.
""".strip()

# ════════════════════════════════════════════════════════════════
# DATA STRUCTURES
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

    def to_dict(self): return asdict(self)
    def operator_summary(self):
        icon = {"URGENT":"🚨","CALLBACK":"⚠️","REQUEST":"📋","QUESTION":"❓","PAYMENT":"💰","SOCIAL":"👍"}.get(self.tier, "•")
        return f"{icon} {self.tier} — {self.client_name}: {self.intent_summary[:60]}"

# ════════════════════════════════════════════════════════════════
# FOCUS MODE AGENT
# ════════════════════════════════════════════════════════════════

class FocusModeAgent:
    def __init__(self, hub_path="cjs_operating_hub.db", operator_name="Jon", business_name="CJS Landscape Solutions"):
        self.hub_path = hub_path
        self._ak = os.getenv("ANTHROPIC_API_KEY", "")
        self.operator_name = operator_name
        self.business_name = business_name

    async def process_incoming(self, message: str, client_name: str, client_phone: str = "", job_id: str = "", dry_run: bool = False) -> FocusModeResult:
        t0 = time.monotonic()
        message_id = f"msg-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}"

        # ── 1. Classify ──────────────────────────────────
        classification = None
        model_used, cost_usd = "", 0.0
        try:
            classification, model_used, cost_usd = await asyncio.wait_for(self._classify(message, client_name), timeout=15.0)
        except Exception as e:
            logger.warning(f"FocusModeAgent: classify failed ({e}) — keyword fallback")
        
        if classification is None: classification = self._keyword_classify(message)

        tier = classification.get("tier", TIER_QUESTION)
        intent_summary = classification.get("intent_summary", message[:60])
        urgency_reason = classification.get("urgency_reason", "")
        suggested_eta = classification.get("suggested_eta", "by end of day")

        # ── 2. Route & Reply ─────────────────────────────
        alert_fired, needs_followup, auto_reply, queue_position = False, False, "", None

        if tier == TIER_URGENT:
            needs_followup = True
            if not dry_run:
                await self._fire_urgent_alert(client_name, message, urgency_reason)
                alert_fired = True
        elif tier == TIER_CALLBACK:
            needs_followup = True
            queue_position = self._persist_message(message_id, client_name, client_phone, message, tier, intent_summary, suggested_eta, job_id, dry_run)
        else:
            try:
                auto_reply = await asyncio.wait_for(self._generate_reply(message, client_name, tier, intent_summary, suggested_eta), timeout=15.0)
            except:
                auto_reply = self._template_reply(client_name, tier, suggested_eta)
            queue_position = self._persist_message(message_id, client_name, client_phone, message, tier, intent_summary, suggested_eta, job_id, dry_run, auto_reply=auto_reply)

        result = FocusModeResult(
            success=True, message_id=message_id, client_name=client_name, tier=tier, confidence=float(classification.get("confidence", 0.7)),
            intent_summary=intent_summary, auto_reply=auto_reply, alert_fired=alert_fired, needs_followup=needs_followup, 
            queue_position=queue_position, suggested_eta=suggested_eta, model_used=model_used, cost_usd=cost_usd, 
            duration_ms=int((time.monotonic() - t0) * 1000)
        )
        logger.info(f"FocusModeAgent: {result.operator_summary()} | reply={'yes' if auto_reply else 'no'}")
        return result

    # ── Internal Helpers ────────────────────────────────────────

    async def _classify(self, message, client_name):
        prompt = CLASSIFY_PROMPT.format(operator_name=self.operator_name, business_name=self.business_name, client_name=client_name, message=message, time_received=datetime.now().strftime("%I:%M %p"))
        text, model, cost = await self._claude(prompt)
        return json.loads(text.strip().replace("```json", "").replace("```", "")), model, cost

    def _keyword_classify(self, message):
        text = message.lower()
        if any(k in text for k in ["flood", "leak", "broken", "urgent"]): return {"tier": TIER_URGENT, "confidence": 0.65}
        if any(k in text for k in ["complaint", "unacceptable"]): return {"tier": TIER_CALLBACK, "confidence": 0.65}
        return {"tier": TIER_QUESTION, "confidence": 0.5}

    async def _generate_reply(self, message, client_name, tier, intent, eta):
        prompt = REPLY_PROMPT.format(operator_name=self.operator_name, business_name=self.business_name, client_name=client_name, message=message, tier=tier, intent_summary=intent, suggested_eta=eta)
        text, _, _ = await self._claude(prompt)
        return text.strip()

    def _template_reply(self, client_name, tier, eta):
        return f"Hi {client_name.split()[0]}, I'm in the field. I'll follow up {eta}. — {self.operator_name}"

    async def _fire_urgent_alert(self, client_name, message, reason):
        try:
            from alerts import dispatch_alert
            await dispatch_alert(title=f"🚨 URGENT — {client_name}", body=f"{message[:120]}", status="red")
        except: logger.warning("Alerts not sent.")

    def _persist_message(self, message_id, client_name, client_phone, message, tier, intent, eta, job_id, dry_run, auto_reply=""):
        if dry_run: return None
        try:
            import sqlite3
            conn = sqlite3.connect(self.hub_path)
            conn.execute("CREATE TABLE IF NOT EXISTS message_queue (id INTEGER PRIMARY KEY, message_id TEXT UNIQUE, client_name TEXT, tier TEXT, intent TEXT, auto_reply TEXT, replied INTEGER DEFAULT 0)")
            conn.execute("INSERT OR IGNORE INTO message_queue (message_id, client_name, tier, intent, auto_reply) VALUES (?,?,?,?,?)", (message_id, client_name, tier, intent, auto_reply))
            conn.commit(); conn.close()
            return 1
        except: return None

    async def _claude(self, prompt, max_tokens=200):
        import anthropic
        client = anthropic.AsyncAnthropic(api_key=self._ak)
        msg = await client.messages.create(model="claude-haiku-4-5-20251001", max_tokens=max_tokens, messages=[{"role": "user", "content": prompt}])
        return msg.content[0].text, "claude-haiku-4-5", 0.0001