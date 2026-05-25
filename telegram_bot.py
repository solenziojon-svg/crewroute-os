import os
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
import asyncio

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ Bot is online and working.")

async def main():
    if not TOKEN:
        print("❌ No TELEGRAM_BOT_TOKEN found!")
        return
        
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    
    print("🤖 Bot is starting...")
    await app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    asyncio.run(main())