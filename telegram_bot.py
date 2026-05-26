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

# Stream logging to standard output for Railway container collection
logging.basicConfig(
    level=logging.INFO, 
    format="%(asctime)s [%(levelname)s] %(message)s", 
    stream=sys.stdout
)
logger = logging.getLogger("crewroute_bot")

async def send_message(session: aiohttp.ClientSession, chat_id: int, text: str) -> None:
    """Dispatches a text message using the shared session connection pool."""
    url = f"{BASE_URL}/sendMessage"
    payload = {"chat_id": chat_id, "text": text}
    try:
        async with session.post(url, json=payload, timeout=10) as resp:
            if resp.status != 200:
                logger.error(f"Failed to send message: HTTP {resp.status}")
    except Exception as e:
        logger.error(f"Network error in send_message: {str(e)}")

async def process_update(session: aiohttp.ClientSession, update: dict) -> None:
    """Processes incoming messages and safely isolates media payloads."""
    message = update.get("message")
    if not message:
        return

    chat_id = message.get("chat", {}).get("id")
    if not chat_id:
        return

    text = message.get("text")
    voice = message.get("voice")
    photo = message.get("photo")

    if voice:
        file_id = voice.get("file_id")
        logger.info(f"Voice log captured for chat {chat_id}: file_id={file_id}")
        await send_message(session, chat_id, "🎙️ Voice log received. Processing optimization route...")
        
    elif photo:
        # Take the highest resolution version (last item in the photo array)
        file_id = photo[-1].get("file_id")
        logger.info(f"Photo captured for chat {chat_id}: file_id={file_id}")
        await send_message(session, chat_id, "📸 Photo confirmation captured. Logging to operational hub...")
        
    elif text == "/start":
        await send_message(session, chat_id, "🚀 CrewRoute Engine Online. Dispatch voice logs or photos to calculate paths.")
        
    elif text:
        await send_message(session, chat_id, "✅ CrewRoute is online. Send me a voice note or photo to log a job.")

async def main():
    logger.info("=========================================")
    logger.info("🚀 Initializing CrewRoute Polling Engine...")
    logger.info("=========================================")
    
    offset = 0
    # Single session instantiation prevents socket leaks and handshake overhead
    async with aiohttp.ClientSession() as session:
        while True:
            try:
                # 30-second long polling timeout keeps resource utilization minimal
                url = f"{BASE_URL}/getUpdates?offset={offset}&timeout=30"
                async with session.get(url, timeout=35) as resp:
                    if resp.status != 200:
                        logger.warning(f"Telegram API warning: HTTP status {resp.status}. Backing off...")
                        await asyncio.sleep(5)
                        continue
                        
                    data = await resp.json()
                    updates = data.get("result", [])
                    
                    for update in updates:
                        offset = update.get("update_id", 0) + 1
                        await process_update(session, update)
                        
            except asyncio.CancelledError:
                logger.info("Shutdown signal acknowledged. Terminating cleanly.")
                break
            except aiohttp.ClientError as ce:
                logger.error(f"Transport network loss: {str(ce)}. Retrying in 5s...")
                await asyncio.sleep(5)
            except Exception as e:
                logger.error(f"Unexpected runtime exception caught: {str(e)}")
                await asyncio.sleep(2)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Engine shutdown by operator.")