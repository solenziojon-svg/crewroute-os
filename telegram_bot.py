import os
import asyncio
import sys
import logging
import aiohttp

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not TOKEN:
    print("CRITICAL: TELEGRAM_BOT_TOKEN environment variable is missing.")
    sys.exit(1)

BASE_URL = f"https://api.telegram.org/bot{TOKEN}"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    stream=sys.stdout
)
logger = logging.getLogger("crewroute_bot")

async def send_message(session: aiohttp.ClientSession, chat_id: int, text: str):
    try:
        async with session.post(
            f"{BASE_URL}/sendMessage",
            json={"chat_id": chat_id, "text": text}
        ) as resp:
            if resp.status != 200:
                logger.error(f"Failed to send message: {resp.status}")
    except Exception as e:
        logger.error(f"Error sending message: {e}")

async def process_update(session: aiohttp.ClientSession, update: dict):
    message = update.get("message")
    if not message:
        return

    chat_id = message.get("chat", {}).get("id")
    if not chat_id:
        return

    text = message.get("text")
    voice = message.get("voice")
    photo = message.get("photo")

    if text == "/start":
        await send_message(session, chat_id, 
            "🚀 CrewRoute Bot is online.\n\n"
            "Send me job notes as text, or a voice note + photo.")

    elif voice:
        # Voice note received
        logger.info(f"Voice note received from chat {chat_id}")
        await send_message(session, chat_id, 
            "🎙️ Voice note logged successfully.")

    elif photo:
        # Photo received
        logger.info(f"Photo received from chat {chat_id}")
        await send_message(session, chat_id, 
            "📸 Photo logged successfully.")

    elif text:
        # Normal text / job notes
        logger.info(f"Text note received from chat {chat_id}")
        preview = text[:120] + "..." if len(text) > 120 else text
        await send_message(session, chat_id, 
            f"✅ Note logged successfully.\n\n{preview}")

async def main():
    logger.info("🚀 CrewRoute Bot starting...")

    offset = 0
    async with aiohttp.ClientSession() as session:
        while True:
            try:
                url = f"{BASE_URL}/getUpdates?offset={offset}&timeout=20"
                async with session.get(url, timeout=25) as resp:
                    if resp.status != 200:
                        await asyncio.sleep(5)
                        continue

                    data = await resp.json()
                    for update in data.get("result", []):
                        offset = update.get("update_id", 0) + 1
                        await process_update(session, update)

            except Exception as e:
                logger.error(f"Error in polling loop: {e}")
                await asyncio.sleep(3)

if __name__ == "__main__":
    asyncio.run(main())