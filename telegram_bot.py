import os
import sys
import logging
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters
)

# Configure logging to stream directly to standard output for Railway log capturing
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    stream=sys.stdout
)
logger = logging.getLogger(__name__)

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles the /start command."""
    if update.message:
        await update.message.reply_text("🤖 Bot is active! Send me text messages, voice notes, or photos.")

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Acknowledges text messages."""
    if update.message:
        await update.message.reply_text("📝 Text message received and acknowledged.")

async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Acknowledges voice notes."""
    if update.message:
        await update.message.reply_text("🎙️ Voice note received and acknowledged.")

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Acknowledges photos."""
    if update.message:
        await update.message.reply_text("📸 Photo received and acknowledged.")

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Catches unhandled errors within handlers to prevent the Railway instance from crashing."""
    logger.error("Exception encountered while handling an update:", exc_info=context.error)
    
    # Optional fallback notification to the user without breaking the poll loop
    if isinstance(update, Update) and update.message:
        try:
            await update.message.reply_text("⚠️ An internal processing error occurred, but the bot remains online.")
        except Exception:
            pass

def main() -> None:
    """Main execution loop."""
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        logger.critical("CRITICAL: TELEGRAM_BOT_TOKEN environment variable is unset. Exiting deployment process.")
        sys.exit(1)

    print("=========================================")
    print("🚀 Initializing Application Platform Engine...")
    print("=========================================")

    # Initialize the high-level application structure
    application = ApplicationBuilder().token(token).build()

    # Route registered core platform handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    application.add_handler(MessageHandler(filters.VOICE, handle_voice))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))

    # Bind the global failure interception route
    application.add_error_handler(error_handler)

    print("🤖 Network architecture established. Starting long polling...")
    print("=========================================")

    # run_polling automatically hooks into SIGINT, SIGTERM, and SIGABRT for clean teardowns
    application.run_polling(close_loop=False)

if __name__ == '__main__':
    main()