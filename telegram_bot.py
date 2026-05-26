import os
import asyncio
import aiohttp

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
BASE_URL = f"https://api.telegram.org/bot{TOKEN}"

async def main():
    print("🤖 Bot is starting...")
    print(f"Token length: {len(TOKEN) if TOKEN else 0}")
    
    async with aiohttp.ClientSession() as session:
        # Send a test message to yourself
        async with session.post(f"{BASE_URL}/getMe") as resp:
            print("getMe response:", await resp.json())

if __name__ == "__main__":
    asyncio.run(main())