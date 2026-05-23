"""
alerts.py
Modular notification system for CrewRoute OS.
Sends clean alerts to Telegram or Discord after every pipeline run.
"""

import os
import logging
from typing import Optional
import requests

logger = logging.getLogger("crewroute.alerts")

# ─────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID   = os.getenv("TELEGRAM_CHAT_ID")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")


# ─────────────────────────────────────────────────────────────
# CORE SENDING FUNCTIONS
# ─────────────────────────────────────────────────────────────

def _send_telegram(message: str, priority: bool = False) -> bool:
    """Send message to Telegram."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.warning("Telegram credentials not set — skipping alert")
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }

    try:
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code == 200:
            return True
        else:
            logger.error(f"Telegram send failed: {response.text}")
            return False
    except Exception as e:
        logger.error(f"Telegram request error: {e}")
        return False


def _send_discord(message: str, priority: bool = False) -> bool:
    """Send message to Discord webhook."""
    if not DISCORD_WEBHOOK_URL:
        logger.warning("Discord webhook not set — skipping alert")
        return False

    # Add priority styling for Discord
    if priority:
        message = f"🚨 **HIGH PRIORITY**\n{message}"

    payload = {"content": message}

    try:
        response = requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=10)
        return response.status_code == 204
    except Exception as e:
        logger.error(f"Discord request error: {e}")
        return False


def send_alert(message: str, priority: bool = False) -> bool:
    """
    Main alert dispatcher.
    Tries Telegram first, then falls back to Discord.
    """
    if not message:
        return False

    # Try Telegram first
    if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
        success = _send_telegram(message, priority=priority)
        if success:
            return True

    # Fallback to Discord
    if DISCORD_WEBHOOK_URL:
        return _send_discord(message, priority=priority)

    logger.warning("No notification channel configured")
    return False


# ─────────────────────────────────────────────────────────────
# HIGH-LEVEL ALERT FUNCTIONS
# ─────────────────────────────────────────────────────────────

def send_run_summary(result) -> None:
    """
    Send summary after a successful pipeline run.
    Called when RunResult.success == True.
    """
    if not result.success:
        return

    plan = result.plan
    governor = result.governor or {}

    lines = [
        "🌿 <b>CrewRoute Daily Run Complete</b>",
        "",
        f"📅 Date: <code>{plan.date}</code>",
        f"👷 Crew: <b>{plan.crew}</b>",
        f"📦 Jobs Optimized: <b>{result.jobs_loaded}</b>",
        f"💰 Total Value: <b>${plan.total_value:,}</b>",
        f"⏱️ Time Saved: <b>{plan.time_saved_mins} mins</b>",
        f"🔄 Method: <code>{plan.method}</code>",
    ]

    if result.dlq_count > 0:
        lines.append(f"⚠️ DLQ Items: <b>{result.dlq_count}</b>")

    # Governor status
    gov_status = governor.get("status", "unknown")
    if gov_status == "green":
        lines.append("✅ Governor: <b>Green</b> — System healthy")
    elif gov_status in ("yellow", "red"):
        lines.append(f"⚠️ Governor: <b>{gov_status.upper()}</b>")
        for flag in governor.get("flags", [])[:3]:  # Limit to top 3
            lines.append(f"   • {flag}")

    lines.append("")
    lines.append("🔗 <a href='https://docs.google.com/spreadsheets/d/YOUR_SHEET_ID'>View Sheet</a>")

    message = "\n".join(lines)
    send_alert(message, priority=(gov_status == "red"))


def send_governor_alert(result) -> None:
    """
    Send high-priority alert when Governor returns yellow or red.
    Focuses on actionable issues (especially DLQ).
    """
    governor = result.governor or {}
    status = governor.get("status")

    if status not in ("yellow", "red"):
        return

    lines = [
        f"🚨 <b>CrewRoute Governor Alert — {status.upper()}</b>",
        "",
        f"📅 Date: <code>{result.plan.date}</code>",
        f"👷 Crew: <b>{result.plan.crew}</b>",
    ]

    # Show governor flags
    flags = governor.get("flags", [])
    if flags:
        lines.append("\n<b>Issues Detected:</b>")
        for flag in flags[:5]:
            lines.append(f"• {flag}")

    # Highlight DLQ if present
    if result.dlq_count > 0:
        lines.append(f"\n⚠️ <b>Dead Letter Queue:</b> {result.dlq_count} items require attention")

    lines.append("\nPlease review and take action from your phone.")

    message = "\n".join(lines)
    send_alert(message, priority=True)