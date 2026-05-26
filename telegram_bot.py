import os
import asyncio
import aiohttp
from datetime import datetime

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
BASE_URL = f"https://api.telegram.org/bot{TOKEN}"

async def send_message(chat_id, text):
    async with aiohttp.ClientSession() as session:
        await session.post(
            f"{BASE_URL}/sendMessage", 
            json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
        )

async def main():
    print("🤖 CrewRoute Bot started successfully")
    
    offset = 0
    async with aiohttp.ClientSession() as session:
        while True:
            try:
                async with session.get(f"{BASE_URL}/getUpdates?offset={offset}&timeout=10") as resp:
                    data = await resp.json()
                    for update in data.get("result", []):
                        offset = update + 1
                        message = update.get("message")
                        if message:
                            chat_id = message  text = message.get("text", "")
                            
                            if text == "/start":
                                await send_message(chat_id, "✅ CrewRoute Bot is online.\n\nSend me a voice note + photo of the job.")
            except Exception as e:
                print(f"Error: {e}")
            await asyncio.sleep(1)

if __name__ == "__main__":
    asyncio.run(main())