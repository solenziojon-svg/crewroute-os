import os
import asyncio
import aiohttp

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
BASE_URL = f"https://api.telegram.org/bot{TOKEN}"

async def send_message(chat_id, text):
    async with aiohttp.ClientSession() as session:
        await session.post(f"{BASE_URL}/sendMessage", json={"chat_id": chat_id, "text": text})

async def main():
    print("🤖 CrewRoute Bot is running...")
    
    offset = 0
    async with aiohttp.ClientSession() as session:
        while True:
            try:
                async with session.get(f"{BASE_URL}/getUpdates?offset={offset}&timeout=5") as resp:
                    data = await resp.json()
                    for update in data.get("result", []):
                        offset = update.get("update_id", 0) + 1
                        message = update.get("message")
                        if message:
                            chat_id = message.get("chat", {}).get("id")
                            await send_message(chat_id, "✅ Bot is online. Send me a voice note or photo.")
            except:
                pass
            await asyncio.sleep(1)

if __name__ == "__main__":
    asyncio.run(main())