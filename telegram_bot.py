import os
import asyncio
import aiohttp
from datetime import datetime

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
BASE_URL = f"https://api.telegram.org/bot{TOKEN}"

async def send_message(chat_id, text):
    async with aiohttp.ClientSession() as session:
        await session.post(f"{BASE_URL}/sendMessage", json={"chat_id": chat_id, "text": text})

async def main():
    print("🤖 Minimal bot starting...")
    print(f"Token exists: {bool(TOKEN)}")
    
    # Test that we can at least start
    await send_message(123456789, "Test message - bot is running")
    print("Bot started successfully")

if __name__ == "__main__":
    asyncio.run(main())