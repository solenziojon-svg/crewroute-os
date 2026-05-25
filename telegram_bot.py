"""
telegram_bot.py — Empire OS Field Entry Point
Simple version for Jon - just send voice note + photo
"""

import os
import asyncio
import aiohttp
from datetime import datetime
from empire_logging import get_logger, bind_context

# Agent imports
from focus_mode_agent import FocusModeAgent
from photo_audit_agent import process_job_completion

logger = get_logger("empire.telegram_bot")

_pending =  # chat_id -> transcript

class EmpireTelegramBot:
    def __init__(self):
        self.token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.openai_key = os.getenv("OPENAI_API_KEY")
        self.base_url = f"https://api.telegram.org/bot{self.token}"
        self.offset = 0
        self.focus_agent = FocusModeAgent()

    async def start(self):
        if not self.token:
            logger.error("No TELEGRAM_BOT_TOKEN found")
            return

        logger.info("telegram_bot_started")
        
        async with aiohttp.ClientSession() as session:
            while True:
                try:
                    updates = await self._get_updates(session)
                    for update in updates:
                        await self._handle_update(session, update)
                except Exception as e:
                    logger.error(f"Error: {e}")
                await asyncio.sleep(1)

    async def _get_updates(self, session):
        url = f"{self.base_url}/getUpdates"
        params = {"offset": self.offset, "timeout": 15}
        async with session.get(url, params=params) as resp:
            data = await resp.json()
            results = data.get("result", [])
            if results:
                self.offset = results[-1] + 1
            return results

    async def _handle_update(self, session, update):
        message = update.get("message")
        if not message:
            return

        chat_id = message  sender = message .get("first_name", "Jon")

        bind_context(chat_id=chat_id, sender=sender)

        # Voice Note
        if "voice" in message:
            await self._reply(session, chat_id, "🎙️ Processing voice note...")
            file_id = message  transcript = await self._transcribe_voice(session, file_id)
            
            _pending = {
                "transcript": transcript,
                "timestamp": datetime.utcnow()
            }
            await self._reply(session, chat_id, "✅ Got it. Now send a photo of the job.")

        # Photo
        elif "photo" in message:
            await self._reply(session, chat_id, "📸 Processing job...")

            file_id = message [-1] photo_url = await self._get_file_url(session, file_id)

            pending = _pending.get(chat_id, {})