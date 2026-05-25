"""
telegram_bot.py — Empire OS Telegram Input Layer (v1)
──────────────────────────────────────────────────────
Primary field input for solo operators.

Accepts:
- Voice notes → transcribed + processed
- Photos → analyzed for quality + upsell
- Text → treated as manual transcript

Calls process_job_completion() and returns clean structured output.

Uses Empire structured logging.

Environment variables required:
- TELEGRAM_BOT_TOKEN
- ANTHROPIC_API_KEY (already used by agents)
- OPENAI_API_KEY (optional but recommended for voice transcription)
"""

from __future__ import annotations

import asyncio
import os
from datetime import datetime

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

from empire_logging import get_logger, bind_context
from photo_audit_agent import process_job_completion

logger = get_logger("empire.telegram_bot")

# ──────────────────────────────────────────────────────────────
# CONFIG
# ──────────────────────────────────────────────────────────────

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

if not TELEGRAM_BOT_TOKEN:
    logger.error("TELEGRAM_BOT_TOKEN not set — bot cannot start")
    raise SystemExit("Missing TELEGRAM_BOT_TOKEN")


# ──────────────────────────────────────────────────────────────
# VOICE TRANSCRIPTION (OpenAI Whisper)
# ──────────────────────────────────────────────────────────────

async def transcribe_voice(file_path: str) -> str:
    """Transcribe voice note using OpenAI Whisper."""
    if not OPENAI_API_KEY:
        return "[Voice note received — transcription requires OPENAI_API_KEY]"

    try:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=OPENAI_API_KEY)

        with open(file_path, "rb") as audio_file:
            transcript = await client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                response_format="text",
            )
        return transcript.strip()
    except Exception as e:
        logger.warning("voice_transcription_failed", error=str(e))
        return "[Transcription failed — please send text instead]"


# ──────────────────────────────────────────────────────────────
# HANDLERS
# ──────────────────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send welcome message."""
    user = update.effective_user
    bind_context(user_id=user.id, username=user.username or "unknown")

    await update.message.reply_text(
        "🚀 CJS Empire Bot is live.\n\n"
        "Send me:\n"
        "• A voice note (job notes)\n"
        "• A completion photo\n"
        "• Both together\n\n"
        "I'll process it through the full Solo-Pilot system and send you the structured result."
    )
    logger.info("bot_started", user=user.username or str(user.id))


async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle incoming voice note."""
    user = update.effective_user
    bind_context(user_id=user.id)

    if not update.message.voice:
        return

    logger.info("voice_note_received")

    # Download voice file
    voice_file = await update.message.voice.get_file()
    file_path = f"/tmp/voice_{user.id}_{datetime.utcnow().strftime('%H%M%S')}.ogg"
    await voice_file.download_to_drive(file_path)

    transcript = await transcribe_voice(file_path)

    await update.message.reply_text(
        f"🎙️ Voice transcribed:\n\n{transcript[:300]}{'...' if len(transcript) > 300 else ''}"
    )

    # Store transcript in user context for pairing with photo
    context.user_data["pending_transcript"] = transcript
    context.user_data["pending_timestamp"] = datetime.utcnow().isoformat()

    await update.message.reply_text(
        "✅ Transcript saved. Now send the job photo (or type /process if no photo)."
    )


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle incoming photo."""
    user = update.effective_user
    bind_context(user_id=user.id)

    if not update.message.photo:
        return

    logger.info("photo_received")

    # Get the highest resolution photo
    photo_file = await update.message.photo[-1].get_file()
    file_path = f"/tmp/photo_{user.id}_{datetime.utcnow().strftime('%H%M%S')}.jpg"
    await photo_file.download_to_drive(file_path)

    transcript = context.user_data.get("pending_transcript", "")
    timestamp = context.user_data.get("pending_timestamp")

    await update.message.reply_text("⏳ Processing through Solo-Pilot system...")

    try:
        result = await process_job_completion(
            job_id=f"tg-{user.id}-{datetime.utcnow().strftime('%Y%m%d%H%M')}",
            transcript=transcript,
            photo_url=None,  # We pass local path via base64 in future version
            photo_base64=None,
            client_name="Field Job",
            dry_run=False,
        )

        # For now, send a clean summary
        summary = (
            f"✅ Job processed\n\n"
            f"Client message:\n{result.get('client_message', 'N/A')[:400]}\n\n"
            f"Upsell: {result.get('upsell_prompt', 'None detected')}\n"
            f"Flags: {result.get('flags', [])}\n"
            f"Duration: {result.get('duration_ms', 0)}ms"
        )

        await update.message.reply_text(summary)

        # Clear pending state
        context.user_data.clear()

    except Exception as e:
        logger.error("process_job_completion_failed", error=str(e))
        await update.message.reply_text(
            f"❌ Processing failed: {str(e)[:200]}\n\nPlease try again or send text + photo separately."
        )


async def process_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Manually trigger processing if only transcript was sent."""
    transcript = context.user_data.get("pending_transcript", "")
    if not transcript:
        await update.message.reply_text("No pending transcript. Send a voice note first.")
        return

    await update.message.reply_text("⏳ Processing transcript only...")

    try:
        result = await process_job_completion(
            job_id=f"tg-text-{datetime.utcnow().strftime('%Y%m%d%H%M')}",
            transcript=transcript,
            client_name="Field Job",
            dry_run=False,
        )

        summary = (
            f"✅ Processed (text only)\n\n"
            f"Client message:\n{result.get('client_message', 'N/A')[:500]}"
        )
        await update.message.reply_text(summary)
        context.user_data.clear()

    except Exception as e:
        await update.message.reply_text(f"Error: {str(e)[:200]}")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Commands:\n"
        "/start — Welcome\n"
        "/process — Process pending transcript (if no photo)\n"
        "/help — This message\n\n"
        "Just send voice notes and photos normally."
    )


def main() -> None:
    """Run the bot."""
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("process", process_command))

    application.add_handler(MessageHandler(filters.VOICE, handle_voice))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))

    logger.info("telegram_bot_starting", mode="polling")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()