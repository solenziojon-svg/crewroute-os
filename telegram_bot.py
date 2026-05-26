from __future__ import annotations

import asyncio
import os
import sys
import logging
import sqlite3
import secrets
from datetime import datetime, timedelta
import aiohttp
import re as _re

# ── Logging Configuration (Railway-friendly) ─────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    stream=sys.stdout
)
logger = logging.getLogger("empire.telegram_bot")

# ── Graceful Imports ─────────────────────────────────────────
try:
    from focus_mode_agent import FocusModeAgent, pending_followups
    HAS_FOCUS = True
except ImportError:
    HAS_FOCUS = False
    logger.warning("focus_mode_agent.py not found")

try:
    from photo_audit_agent import process_job_completion
    HAS_PHOTO = True
except ImportError:
    HAS_PHOTO = False
    logger.warning("photo_audit_agent.py not found")

try:
    from crewroute_agents import SoloPilotAgent
    HAS_SOLO = True
except ImportError:
    HAS_SOLO = False
    logger.warning("SoloPilotAgent not found — using fallback parser")

# ── In-Memory State for Voice + Photo Pairing ────────────────
_pending: dict[int, dict] = {}
_SESSION_TTL = timedelta(minutes=10)
_last_auto_reply: dict[int, datetime] = {}   # For Focus Mode debounce


# ═════════════════════════════════════════════════════════════
# DATABASE LAYER
# ═════════════════════════════════════════════════════════════

class CrewRouteDB:
    def __init__(self, db_path: str = "cjs_operating_hub.db"):
        self.db_path = db_path
        self._init_db()

    def _get_connection(self):
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS crewroute_jobs (
                    id TEXT PRIMARY KEY,
                    chat_id INTEGER NOT NULL,
                    client_name TEXT DEFAULT 'Pending',
                    raw_text TEXT,
                    price REAL,
                    planned_duration INTEGER,
                    actual_duration INTEGER,
                    voice_file_id TEXT,
                    photo_file_ids TEXT,
                    status TEXT DEFAULT 'logged',
                    created_at TEXT DEFAULT (datetime('now'))
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_cr_jobs_chat ON crewroute_jobs(chat_id)")
            conn.commit()

    def insert_job(self, job_data: dict) -> str:
        job_id = job_data.get("id") or secrets.token_hex(8)

        photos = job_data.get("photo_file_ids", [])
        if isinstance(photos, list):
            photo_str = ",".join(photos)
        else:
            photo_str = str(photos) if photos else ""

        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO crewroute_jobs (
                    id, chat_id, client_name, raw_text, price,
                    planned_duration, actual_duration, voice_file_id,
                    photo_file_ids, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                job_id,
                job_data["chat_id"],
                job_data.get("client_name", "Pending"),
                job_data.get("raw_text"),
                job_data.get("price"),
                job_data.get("planned_duration"),
                job_data.get("actual_duration"),
                job_data.get("voice_file_id"),
                photo_str,
                job_data.get("status", "logged")
            ))
            conn.commit()
        return job_id

    def get_count(self) -> int:
        try:
            with self._get_connection() as conn:
                row = conn.execute("SELECT COUNT(*) as cnt FROM crewroute_jobs").fetchone()
                return row["cnt"] if row else 0
        except Exception:
            return 0


# ═════════════════════════════════════════════════════════════
# PARSING HELPERS
# ═════════════════════════════════════════════════════════════

_JOB_NOTE_KEYWORDS = [
    "finished", "done", "completed", "wrapped up", "just did",
    "knocked out", "mowed", "edged", "trimmed", "fertilized",
    "sprinkler", "irrigation", "pruned", "blew out", "cleaned up",
]

def _is_job_note(text: str) -> bool:
    t = text.lower()
    return any(kw in t for kw in _JOB_NOTE_KEYWORDS)

def parse_telegram_message(text: str | None = None, chat_id: int | None = None) -> dict:
    job = {
        "chat_id": chat_id,
        "client_name": "Pending",
        "raw_text": text,
        "price": None,
        "planned_duration": None,
        "actual_duration": None,
        "voice_file_id": None,
        "photo_file_ids": [],
        "work_items": [],
        "status": "logged",
    }

    if not text:
        return job

    text_lower = text.lower()

    # Client name
    name_match = _re.search(
        r"(?i)(?:for|note for|job for|at|finished at|done at|wrapped up(?: at)?)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3})",
        text
    )
    if name_match:
        job["client_name"] = name_match.group(1).strip()

    # Duration
    dur_match = _re.search(r"(\d+(?:\.\d+)?)\s*(min|mins|minute|minutes|hr|hrs|hour|hours)", text_lower)
    if dur_match:
        val = float(dur_match.group(1))
        unit = dur_match.group(2).lower()
        job["planned_duration"] = int(val * 60) if "h" in unit else int(val)

    # Price
    price_match = _re.search(r"\$(\d[\d,]*(?:\.\d{2})?)", text)
    if price_match:
        job["price"] = float(price_match.group(1).replace(",", ""))

    # Work items
    work_kw = {
        "lawn": "Lawn", "mow": "Mowing", "edge": "Edging", "trim": "Trimming",
        "fertili": "Fertilization", "weed": "Weed control", "irrigat": "Irrigation",
        "sprinkler": "Sprinkler", "prune": "Pruning", "mulch": "Mulching",
        "blow": "Blowout", "repair": "Repair", "install": "Installation",
    }
    for kw, label in work_kw.items():
        if kw in text_lower and label not in job["work_items"]:
            job["work_items"].append(label)

    return job

def _extract_job_context(text: str) -> dict:
    res = parse_telegram_message(text=text)
    return {
        "client_name": res["client_name"] if res["client_name"] != "Pending" else "",
        "duration_mins": res["planned_duration"] or 0,
        "value": int(res["price"] or 0),
        "work_items": res["work_items"],
    }

def _build_confirmation(client_name: str, work_items: list, duration_mins: int, value: int, follow_up: str = "") -> str:
    parts = ["✅ Job logged"]
    if client_name:
        parts.append(f"for *{client_name}*")
    if duration_mins:
        parts.append(f"{duration_mins} min")
    if value:
        parts.append(f"${value:,}")

    lines = [" – ".join(parts)]
    if work_items:
        lines.append(f"🔧 {', '.join(work_items)}")
    if follow_up:
        lines.append(f"📌 {follow_up}")
    return "\n".join(lines)


# ═════════════════════════════════════════════════════════════
# MAIN BOT
# ═════════════════════════════════════════════════════════════

class EmpireTelegramBot:
    def __init__(self):
        self.token = os.getenv("TELEGRAM_BOT_TOKEN", "")
        self.openai_key = os.getenv("OPENAI_API_KEY", "")
        self.base_url = f"https://api.telegram.org/bot{self.token}"
        self.hub_path = os.getenv("HUB_DB_PATH", "cjs_operating_hub.db")
        self.crew = os.getenv("DEFAULT_CREW", "Solo")
        self.op_id = os.getenv("OPERATOR_CHAT_ID", "")
        self.offset = 0

        self.db = CrewRouteDB(self.hub_path)
        self.focus = FocusModeAgent(hub_path=self.hub_path) if HAS_FOCUS else None
        self.solo_agent = SoloPilotAgent(hub_path=self.hub_path) if HAS_SOLO else None

    async def start(self):
        if not self.token:
            print("❌ TELEGRAM_BOT_TOKEN is missing")
            return

        logger.info("telegram_bot_started")
        print("🤖 Empire Telegram Bot is online")

        async with aiohttp.ClientSession() as session:
            while True:
                try:
                    updates = await self._get_updates(session)
                    for update in updates:
                        try:
                            await self._handle_update(session, update)
                        except Exception as e:
                            logger.error(f"update_failed: {e}")
                except Exception as e:
                    logger.error(f"poll_failed: {e}")
                    await asyncio.sleep(5)
                await asyncio.sleep(1)

    async def _handle_update(self, session, update):
        msg = update.get("message")
        if not msg:
            return

        chat_id = msg["chat"]["id"]
        sender = msg["from"].get("first_name", "Field User")

        if self.op_id and str(chat_id) != self.op_id:
            await self._reply(session, chat_id, "This bot is private.")
            return

        if "voice" in msg:
            await self._on_voice(session, chat_id, msg["voice"]["file_id"])
        elif "photo" in msg:
            await self._on_photo(session, chat_id, msg["photo"][-1]["file_id"])
        elif "text" in msg:
            await self._on_text(session, chat_id, sender, msg["text"].strip())

    # ── Voice Note ───────────────────────────────────────────
    async def _on_voice(self, session, chat_id, file_id):
        await self._reply(session, chat_id, "🎙️ Voice note received. Send a photo to complete.")

        _pending[chat_id] = {
            "transcript": "",
            "photo_file_id": _pending.get(chat_id, {}).get("photo_file_id", ""),
            "timestamp": datetime.utcnow()
        }

        transcript = await self._transcribe(session, file_id)
        _pending[chat_id]["transcript"] = transcript

        if _pending[chat_id].get("photo_file_id"):
            await self._execute_pipeline(session, chat_id)

    # ── Photo ────────────────────────────────────────────────
    async def _on_photo(self, session, chat_id, file_id):
        await self._reply(session, chat_id, "📸 Photo received.")

        if chat_id in _pending and _pending[chat_id].get("transcript"):
            _pending[chat_id]["photo_file_id"] = file_id
            await self._execute_pipeline(session, chat_id)
        else:
            _pending[chat_id] = {
                "transcript": "",
                "photo_file_id": file_id,
                "timestamp": datetime.utcnow()
            }
            await asyncio.sleep(2.5)

            if chat_id in _pending and _pending[chat_id].get("transcript"):
                await self._execute_pipeline(session, chat_id)
            else:
                # Standalone photo
                self.db.insert_job({
                    "chat_id": chat_id,
                    "client_name": "Pending",
                    "raw_text": "Photo-only log",
                    "photo_file_ids": file_id,
                    "status": "logged"
                })
                await self._reply(session, chat_id, "✅ Photo logged.")

    async def _execute_pipeline(self, session, chat_id):
        p = _pending.pop(chat_id, {})
        transcript = p.get("transcript", "")
        photo_file_id = p.get("photo_file_id", "")

        photo_url = await self._get_file_url(session, photo_file_id)

        if not HAS_PHOTO:
            ctx = _extract_job_context(transcript)
            self.db.insert_job({
                "chat_id": chat_id,
                "client_name": ctx["client_name"] or "Pending",
                "raw_text": transcript or "Photo + voice log",
                "price": ctx["value"],
                "planned_duration": ctx["duration_mins"],
                "voice_file_id": "transcribed",
                "photo_file_ids": photo_file_id,
                "status": "logged"
            })
            await self._reply(session, chat_id, "✅ Job logged (voice + photo).")
            return

        try:
            result = await asyncio.wait_for(
                process_job_completion(
                    job_id=f"tg-{chat_id}-{datetime.utcnow():%Y%m%d%H%M%S}",
                    transcript=transcript,
                    photo_url=photo_url,
                    client_name="Field",
                    crew=self.crew,
                    date=datetime.utcnow().strftime("%Y-%m-%d"),
                    hub_path=self.hub_path,
                ),
                timeout=50.0
            )

            ctx = _extract_job_context(transcript)
            self.db.insert_job({
                "chat_id": chat_id,
                "client_name": ctx["client_name"] or "Pending",
                "raw_text": transcript,
                "price": ctx["value"],
                "planned_duration": ctx["duration_mins"],
                "voice_file_id": "processed",
                "photo_file_ids": photo_file_id,
                "status": "processed"
            })

            await self._reply(session, chat_id, self._format_completion(result))

        except Exception as e:
            logger.error(f"pipeline_failed: {e}")
            await self._reply(session, chat_id, "❌ Pipeline failed.")

    # ── Text Job Notes + Focus Mode ──────────────────────────
    async def _on_text(self, session, chat_id, sender, text):
        if text.startswith(("/start", "/help")):
            await self._reply(session, chat_id, 
                "🚀 CrewRoute Bot is online.\nSend job notes as text or voice + photo.")
            return

        # Job note path
        if _is_job_note(text):
            ctx = _extract_job_context(text)
            await self._reply(session, chat_id, "📋 Logging job note...")

            job_id = self.db.insert_job({
                "chat_id": chat_id,
                "client_name": ctx["client_name"] or "Pending",
                "raw_text": text,
                "price": ctx["value"],
                "planned_duration": ctx["duration_mins"],
                "status": "logged"
            })

            conf = _build_confirmation(
                client_name=ctx["client_name"],
                work_items=ctx["work_items"],
                duration_mins=ctx["duration_mins"],
                value=ctx["value"]
            )
            await self._reply(session, chat_id, f"{conf}\nID: `{job_id}`")
            return

        # Focus Mode path with debounce (anti-spam)
        if HAS_FOCUS and self.focus:
            # Debounce: only auto-reply if 12+ seconds have passed
            last = _last_auto_reply.get(chat_id)
            if last and (datetime.utcnow() - last).total_seconds() < 12:
                return

            result = await self.focus.process_incoming(message=text, client_name=sender, dry_run=False)
            _last_auto_reply[chat_id] = datetime.utcnow()

            if result.tier == "URGENT":
                await self._reply(session, chat_id, f"🚨 *URGENT* — {result.intent_summary}")
            elif result.auto_reply:
                await self._reply(session, chat_id, f"✅ *Auto-replied ({result.tier}):*\n_{result.auto_reply}_")
            return

        await self._reply(session, chat_id, "✅ Received. Send a job note to log work.")

    # ── Helpers ──────────────────────────────────────────────
    async def _get_updates(self, session):
        try:
            async with session.get(
                f"{self.base_url}/getUpdates",
                params={"offset": self.offset, "timeout": 20},
                timeout=aiohttp.ClientTimeout(total=25)
            ) as resp:
                if resp.status != 200:
                    return []
                data = await resp.json()
                results = data.get("result", [])
                if results:
                    self.offset = results[-1]["update_id"] + 1
                return results
        except Exception:
            return []

    async def _transcribe(self, session, file_id):
        if not self.openai_key:
            return "[OPENAI_API_KEY not set]"
        # Add your full Whisper transcription logic here
        return "[Transcription placeholder]"

    async def _get_file_url(self, session, file_id):
        async with session.get(f"{self.base_url}/getFile", params={"file_id": file_id}) as r:
            path = (await r.json())["result"]["file_path"]
        return f"https://api.telegram.org/file/bot{self.token}/{path}"

    async def _reply(self, session, chat_id, text):
        try:
            await session.post(
                f"{self.base_url}/sendMessage",
                json={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"},
                timeout=10
            )
        except Exception as e:
            logger.warning(f"reply_failed: {e}")


if __name__ == "__main__":
    bot = EmpireTelegramBot()
    asyncio.run(bot.start())