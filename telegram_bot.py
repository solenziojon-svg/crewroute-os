import os
import asyncio
import aiohttp
from datetime import datetime

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
BASE_URL = f"https://api.telegram.org/bot{TOKEN}"

async def send_message(chat_id, text):
    async with aiohttp.ClientSession() as session:
        await session.post(f"{BASE_URL}/sendMessage", json={"chat_id": chat_id, "text": text})

async def handle_update(update):
    message = update.get("message")
    if not message:
        return
        
    chat_id = message.get("chat", {}).get("id")
    text = message.get("text", "")
    
    if text == "/start":
        await send_message(chat_id, "✅ Bot is online and working.\nSend me a voice note + photo of a job.")

async def main():
    print("🤖 Minimal bot starting...")
    print(f"Token exists: {bool(TOKEN)}")
    
    offset = 0
    async with aiohttp.ClientSession() as session:
        while True:
            try:
                url = f"{BASE_URL}/getUpdates?offset={offset}&timeout=10"
                async with session.get(url) as resp:
                    data = await resp.json()
                    for update in data.get("result", []):
                        offset = update + 1
                        await handle_update(update)
            except Exception as e:
                print(f"Error: {e}")
            await asyncio.sleep(1)

if __name__ == "__main__":
    asyncio.run(main())