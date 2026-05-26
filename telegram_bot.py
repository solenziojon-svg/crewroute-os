import os
import asyncio
import aiohttp
import logging
from datetime import datetime

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("crewroute_bot")

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
BASE_URL = f"https://api.telegram.org/bot{TOKEN}"
DOWNLOAD_DIR = "downloads"

# Ensure download directory exists
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

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

async def download_telegram_file(session: aiohttp.ClientSession, file_id: str, chat_id: int, file_type: str = "file"):
    try:
        # Get file path
        async with session.get(f"{BASE_URL}/getFile?file_id={file_id}") as resp:
            data = await resp.json()
            file_path = data.get("result", {}).get("file_path")
            if not file_path:
                logger.error("No file_path received")
                return None

        # Download the file
        download_url = f"https://api.telegram.org/file/bot{TOKEN}/{file_path}"
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{chat_id}_{timestamp}_{os.path.basename(file_path)}"
        local_path = os.path.join(DOWNLOAD_DIR, filename)

        async with session.get(download_url) as resp:
            if resp.status != 200:
                logger.error(f"Download failed: {resp.status}")
                return None

            with open(local_path, "wb") as f:
                async for chunk in resp.content.iter_chunked(8192):
                    f.write(chunk)

        logger.info(f"Downloaded {file_type} to {local_path}")
        return local_path

    except Exception as e:
        logger.error(f"Error downloading {file_type}: {e}")
        return None

async def main():
    logger.info("🚀 CrewRoute Bot starting...")

    offset = 0
    async with aiohttp.ClientSession() as session:
        while True:
            try:
                async with session.get(f"{BASE_URL}/getUpdates?offset={offset}&timeout=15") as resp:
                    data = await resp.json()
                    for update in data.get("result", []):
                        offset = update.get("update_id", 0) + 1
                        message = update.get("message")
                        if not message:
                            continue

                        chat_id = message.get("chat", {}).get("id")
                        text = message.get("text")
                        voice