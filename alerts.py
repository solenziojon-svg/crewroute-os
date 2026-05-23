```python
"""
alerts.py (v1.4 - PRODUCTION GATED)
─────────────────────────────────────────────────────
Adaptive alerting client translating and formatting summaries 
dynamically based on notification channels (Telegram HTML / Discord Markdown).
Uses zero external dependencies.
"""

import os
import json
import logging
import urllib.request
import urllib.error
from typing import Optional

logger = logging.getLogger("crewroute.alerts")

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID   = os.getenv("TELEGRAM_CHAT_ID")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

def _translate_html_to_markdown(html_text: str) -> str:
    """Converts standard HTML formatting elements to compliant Discord markdown."""
    markdown_text = html_text.replace("<b>", "**").replace("</b>", "**")
    markdown_text = markdown_text.replace("<i>", "*").replace("</i>", "*")
    return markdown_text

def _send_telegram(message: str, priority: bool = False) -> bool:
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }

    try:
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=body,
            method="POST",
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            return response.getcode() == 200
    except Exception as e:
        logger.error(f"Telegram request error: {e}")
        return False

def _send_discord(message: str, priority: bool = False) -> bool:
    if not DISCORD_WEBHOOK_URL:
        return False

    # Dynamically translate HTML to clean markdown for Discord display
    formatted_message = _translate_html_to_markdown(message)
    if priority:
        formatted_message = f"🚨 **HIGH PRIORITY**\n{formatted_message}"

    payload = {"content": formatted_message}

    try:
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            DISCORD_WEBHOOK_URL,
            data=body,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "User-Agent": "CrewRoute-OS/1.0"
            }
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            return response.getcode() in (200, 204)
    except Exception as e:
        logger.error(f"Discord request error: {e}")
        return False

def send_alert(message: str, priority: bool = False) -> bool:
    if not message:
        return False

    if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
        success = _send_telegram(message, priority=priority)
        if success:
            return True

    if DISCORD_WEBHOOK_URL:
        return _send_discord(message, priority=priority)

    logger.warning("No notification channel configured")
    return False

async def dispatch_alert(title: str, body: str, status: str = "green") -> bool:
    """Async entry point matching the collaborator routing contract."""
    emoji_map = {"green": "✅", "yellow": "⚠️", "red": "🚨"}
    emoji = emoji_map.get(status.lower(), "🌿")
    
    formatted_message = (
        f"{emoji} <b>{title}</b>\n\n"
        f"{body}\n\n"
        f"<i>Status Flag: {status.upper()}</i>"
    )
    
    priority = status.lower() in ("yellow", "red")
    
    # Run the blocking network call safely in executor threads
    try:
        import asyncio
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, send_alert, formatted_message, priority)
    except Exception as e:
        # Fallback to direct synchronous execution
        return send_alert(formatted_message, priority)

def send_run_summary(result) -> None:
    if not result.success:
        return

    plan = result.plan
    governor = result.governor or {}

    lines = [
        "🌿 <b>CrewRoute Daily Run Complete</b>",
        "",
        f"📅 Date: {plan.date}",
        f"👷 Crew: {plan.crew}",
        f"📦 Jobs Optimized: {result.jobs_loaded}",
        f"💰 Total Value: ${plan.total_value:,}",
        f"⏱️ Time Saved: {plan.time_saved_mins} mins",
        f"🔄 Method: {plan.method}",
    ]

    if result.dlq_count > 0:
        lines.append(f"⚠️ DLQ Items: {result.dlq_count}")

    gov_status = governor.get("status", "unknown")
    if gov_status == "green":
        lines.append("✅ Governor: Green — System healthy")
    elif gov_status in ("yellow", "red"):
        lines.append(f"⚠️ Governor: {gov_status.upper()}")
        for flag in governor.get("flags", [])[:3]:
            lines.append(f"   • {flag}")

    message = "\n".join(lines)
    send_alert(message, priority=(gov_status == "red"))

def send_governor_alert(result) -> None:
    governor = result.governor or {}
    status = governor.get("status")

    if status not in ("yellow", "red"):
        return

    lines = [
        f"🚨 <b>CrewRoute Governor Alert — {status.upper()}</b>",
        "",
        f"📅 Date: {result.plan.date}",
        f"👷 Crew: {result.plan.crew}",
    ]

    flags = governor.get("flags", [])
    if flags:
        lines.append("\nIssues Detected:")
        for flag in flags[:5]:
            lines.append(f"• {flag}")

    if result.dlq_count > 0:
        lines.append(f"\n⚠️ Dead Letter Queue: {result.dlq_count} items require attention")

    lines.append("\nPlease review and take action from your phone.")
    message = "\n".join(lines)
    send_alert(message, priority=True)

```
