import os
import asyncio
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ Bot is online.\nSend me a voice note, photo, or text to log a job.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    
    if message.text:
        text = message.text.strip()
        await message.reply_text(f"📝 Received:\n{text[:150]}...")
    elif message.voice or message.photo:
        await message.reply_text("🎙️📸 Received media. Job logged.")
    else:
        await message.reply_text("✅ Got your message.")

async def main():
    if not TOKEN:
        print("❌ No TELEGRAM_BOT_TOKEN found!")
        return
        
    print("🤖 CrewRoute Bot started successfully")
    
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.ALL, handle_message))
    
    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())