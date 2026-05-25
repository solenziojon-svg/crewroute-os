"""
telegram_bot.py — Empire OS Field Entry Point (Burn & Replace v2)
──────────────────────────────────────────────────────────────────
Handles voice notes + photos from the field and routes them
through the full Solo-Pilot pipeline (SoloPilotAgent + PhotoAuditAgent).

Usage:
    python telegram_bot.py
"""

import os
import asyncio
import aiohttp
from datetime import datetime, timedelta
from empire_logging import get_logger, bind_context

# Agent imports
from focus_mode_agent import FocusModeAgent
from photo_audit_agent import process_job_completion

logger = get_logger("empire.telegram_bot")

# Simple in-memory state to pair voice + photo from same chat
# In production you can move this to Redis or the Hub if needed
_pending_transcripts = {}  # chat_id -> {"transcript": str, "timestamp": datetime}


class EmpireTelegramBot:
    def __init__(self):
        self.token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.openai_key = os.getenv("OPENAI_API_KEY")
        self.base_url = f"https://api.telegram.org/bot{self.token}"
        self.offset = 0
        self.focus_agent = FocusModeAgent()

    async def start(self):
        if not self.token:
            logger.error("telegram_bot_boot_failed", reason="missing_TELEGRAM_BOT_TOKEN")
            return

        logger.info("telegram_bot_started", status="operational")

        async with aiohttp.ClientSession() as session:
            while True:
                try:
                    updates = await self._get_updates(session)
                    for update in updates:
                        await self._handle_update(session, update)
                except Exception as e:
                    logger.error("polling_error", error=str(e))
                await asyncio.sleep(1)

    async def _get_updates(self, session: aiohttp.ClientSession):
        url = f"{self.base_url}/getUpdates"
        params = {"offset": self.offset, "timeout": 15}
        async with session.get(url, params=params) as resp:
            if resp.status != 200:
                return []
            data = await resp.json()
            results = data.get("result", [])
            if results:
                self.offset = results[-1]["update_id"] + 1
            return results

    async def _handle_update(self, session: aiohttp.ClientSession, update: dict):
        message = update.get("message")
        if not message:
            return

        chat_id = message["chat"]["id"]
        sender = message["from"].get("first_name", "Field User")

        bind_context(chat_id=chat_id, sender=sender)

        # ── Voice Note ────────────────────────────────────────
        if "voice" in message:
            logger.info("voice_note_received")
            await self._reply(session, chat_id, "🎙️ Transcribing voice note...")

            file_id = message["voice"]["file_id"]
            transcript = await self._transcribe_voice(session, file_id)

            if transcript.startswith("["):
                await self._reply(session, chat_id, transcript)
                return

            # Store transcript temporarily so next photo can pair with it
            _pending_transcripts[chat_id] = {
                "transcript": transcript,
                "timestamp": datetime.utcnow()
            }

            await self._reply(session, chat_id, f"✅ Transcript captured.\n\nNow send the job photo to complete the entry.")

        # ── Photo ─────────────────────────────────────────────
        elif "photo" in message:
            logger.info("photo_received")
            await self._reply(session, chat_id, "📸 Analyzing photo + running full pipeline...")

            file_id = message["photo"][-1]["file_id"]
            photo_url = await self._get_file_url(session, file_id)

            # Check if we have a recent voice transcript for this chat
            pending = _pending_transcripts.get(chat_id)
            transcript = ""
            if pending and (datetime.utcnow() - pending["timestamp"]) < timedelta(minutes=10):
                transcript = pending["transcript"]

            try:
                result = await process_job_completion(
                    job_id=f"tg-{chat_id}-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
                    transcript=transcript,
                    photo_url=photo_url,
                    client_name=sender,
                    dry_run=False,
                )

                # Build clean reply for the user
                reply_text = "✅ Job processed\n\n"
                if result.get("client_message"):
                    reply_text += f"**Client Message:**\n{result['client_message'][:600]}\n\n"
                if result.get("upsell_prompt"):
                    reply_text += f"**Upsell Detected:** {result['upsell_prompt']}\n\n"
                if result.get("flags"):
                    reply_text += f"**Flags:** {', '.join(result['flags'])}\n"

                await self._reply(session, chat_id, reply_text)

                # Clear pending transcript after successful processing
                if chat_id in _pending_transcripts:
                    del _pending_transcripts[chat_id]

            except Exception as e:
                logger.error("process_job_completion_failed", error=str(e))
                await self._reply(session, chat_id, f"❌ Processing failed: {str(e)[:200]}")

        # ── Text Message (Focus Mode) ─────────────────────────
        elif "text" in message:
            text = message["text"].strip()

            if text.startswith("/start"):
                await self._reply(session, chat_id, 
                    "🚀 Empire Field Bot is live.\n\n"
                    "Send a voice note + photo to process a job completion.\n"
                    "Or just send text for Focus Mode classification.")
                return

            if text.startswith("/help"):
                await self._reply(session, chat_id, 
                    "Commands:\n/start — Welcome message\n"
                    "Just send voice + photo for full processing.\n"
                    "Text messages go through Focus Mode Shield.")
                return

            # Normal text → FocusModeAgent
            result = await self.focus_agent.process_incoming(
                message=text,
                client_name=sender,
                dry_run=False
            )

            if result.auto_reply:
                await self._reply(session, chat_id, result.auto_reply)
            elif result.tier == "URGENT":
                await self._reply(session, chat_id, "🚨 URGENT flagged. Alert sent to operator.")

    async def _transcribe_voice(self, session: aiohttp.ClientSession, file_id: str) -> str:
        if not self.openai_key:
            return "[OPENAI_API_KEY not configured]"

        # Get file path from Telegram
        file_resp = await session.get(f"{self.base_url}/getFile", params={"file_id": file_id})
        file_data = await file_resp.json()
        file_path = file_data["result"]["file_path"]
        download_url = f"https://api.telegram.org/file/bot{self.token}/{file_path}"

        # Download file
        file_content = await session.get(download_url)
        file_bytes = await file_content.read()

        # Send to OpenAI Whisper
        form = aiohttp.FormData()
        form.add_field("file", file_bytes, filename="voice.ogg", content_type="audio/ogg")
        form.add_field("model", "whisper-1")

        headers = {"Authorization": f"Bearer {self.openai_key}"}
        whisper_resp = await session.post(
            "https://api.openai.com/v1/audio/transcriptions",
            data=form,
            headers=headers
        )
        result = await whisper_resp.json()
        return result.get("text", "[Transcription failed]")

    async def _get_file_url(self, session: aiohttp.ClientSession, file_id: str) -> str:
        resp = await session.get(f"{self.base_url}/getFile", params={"file_id": file_id})
        data = await resp.json()
        path = data["result"]["file_path"]
        return f"https://api.telegram.org/file/bot{self.token}/{path}"

    async def _reply(self, session: aiohttp.ClientSession, chat_id: int, text: str):
        url = f"{self.base_url}/sendMessage"
        await session.post(url, json={
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "Markdown"
        })


if __name__ == "__main__":
    bot = EmpireTelegramBot()
    asyncio.run(bot.start())