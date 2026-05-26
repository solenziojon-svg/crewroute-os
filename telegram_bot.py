import os
import asyncio
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "✅ <b>CrewRoute Bot Online</b>\n\n"
        "Send me a voice note + photo, or just text to log a job.",
        parse_mode="HTML"
    )

async def handle_job(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    text = message.text or ""
    chat_id = message.chat_id

    await message.reply_text("✅ Job received. Logging now...")

    # Simple acknowledgment for now
    summary = f"Job logged for client.\n\n{text[:100]}..." if text else "Voice note or photo received."
    await message.reply_text(f"📝 {summary}")

async def main():
    if not TOKEN:
        print("❌ No TELEGRAM_BOT_TOKEN found!")
        return

    print("🤖 CrewRoute Bot started successfully")

    app = Application.builder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT | filters.VOICE | filters.PHOTO, handle_job))

    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())