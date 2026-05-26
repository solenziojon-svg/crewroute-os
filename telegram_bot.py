import os
import asyncio
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "✅ <b>CrewRoute Bot Online</b>\n\n"
        "Send me a voice note + photo to log a job.",
        parse_mode="HTML"
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    if message.voice or message.photo:
        await message.reply_text("📸 Processing your job... I'll analyze it shortly.")
    elif message.text:
        await message.reply_text(f"Received: {message.text}")

async def main():
    if not TOKEN:
        print("❌ No TELEGRAM_BOT_TOKEN found!")
        return

    print("🤖 CrewRoute Bot starting...")

    app = Application.builder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT | filters.VOICE | filters.PHOTO, handle_message))

    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())