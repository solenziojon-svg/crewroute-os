"""
analyze_photo_route.py — /api/analyze-photo backend endpoint
──────────────────────────────────────────────────────────────
FastAPI route for Railway deployment.

Accepts a photo upload, calls Claude Vision, returns structured JSON.
Keeps the API key server-side — never exposed to the browser.

Add to main.py:
    from analyze_photo_route import router as photo_router
    app.include_router(photo_router, prefix="/api")

Usage:
    POST /api/analyze-photo
    Content-Type: multipart/form-data
    Body: photo (file), job_id (optional str), lat/lng (optional float)

    Returns: { job_id, captured_at, location, quality,
               work_completed, upsell, client_message_draft,
               flags, raw_description }
"""

import base64
import json
import logging
import os
from datetime import datetime
from typing import Optional

import httpx
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse

logger = logging.getLogger("crewroute.photo")
router = APIRouter(tags=["photo"])

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL      = "claude-sonnet-4-20250514"

VISION_PROMPT = """You are a professional landscaping job quality auditor.
Analyze this photo of completed landscaping work.

Return ONLY valid JSON with no markdown, no preamble:
{
  "quality": {
    "score": <1-10 integer>,
    "status": "verified" | "acceptable" | "needs_attention" | "failed",
    "notes": "<one sentence description>"
  },
  "work_completed": ["<service 1>", "<service 2>"],
  "upsell": {
    "detected": <true|false>,
    "description": "<opportunity or empty string>",
    "estimated_value": <dollar integer, 0 if none>
  },
  "client_message_draft": "<2-3 sentence professional message>",
  "flags": ["<operator alerts>"],
  "raw_description": "<one sentence of what is visible>"
}

Score: 10=perfect, 7-9=good, 4-6=acceptable, 1-3=below standard."""


@router.post("/analyze-photo")
async def analyze_photo(
    photo:  UploadFile         = File(...),
    job_id: Optional[str]      = Form(None),
    lat:    Optional[float]    = Form(None),
    lng:    Optional[float]    = Form(None),
):
    """
    Accepts a photo, calls Claude Vision, returns structured job audit JSON.
    ANTHROPIC_API_KEY is read server-side — never sent to the browser.
    """
    if not ANTHROPIC_API_KEY:
        raise HTTPException(status_code=500, detail="ANTHROPIC_API_KEY not set")

    # ── Read + encode photo ───────────────────────────────────
    photo_bytes = await photo.read()
    if len(photo_bytes) > 10 * 1024 * 1024:  # 10MB limit
        raise HTTPException(status_code=413, detail="Photo too large (max 10MB)")

    media_type = photo.content_type or "image/jpeg"
    base64_img = base64.b64encode(photo_bytes).decode("utf-8")
    computed_job_id = job_id or _generate_job_id()

    # ── Call Claude Vision ────────────────────────────────────
    payload = {
        "model":      CLAUDE_MODEL,
        "max_tokens": 1000,
        "messages": [{
            "role": "user",
            "content": [
                {
                    "type":   "image",
                    "source": {
                        "type":       "base64",
                        "media_type": media_type,
                        "data":       base64_img,
                    }
                },
                { "type": "text", "text": VISION_PROMPT }
            ]
        }]
    }

    try:
        async with httpx.AsyncClient(timeout=45.0) as client:
            resp = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "Content-Type":      "application/json",
                    "x-api-key":         ANTHROPIC_API_KEY,
                    "anthropic-version": "2023-06-01",
                },
                json=payload,
            )
            resp.raise_for_status()
    except httpx.HTTPStatusError as e:
        logger.error(f"Claude API HTTP error: {e.response.status_code} {e.response.text[:200]}")
        raise HTTPException(status_code=502, detail=f"Vision API error: {e.response.status_code}")
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Vision API timed out")
    except Exception as e:
        logger.error(f"Claude API call failed: {e}")
        raise HTTPException(status_code=502, detail="Vision API unavailable")

    # ── Parse response ────────────────────────────────────────
    data    = resp.json()
    raw     = data.get("content", [{}])[0].get("text", "")
    clean   = raw.replace("```json", "").replace("```", "").strip()

    try:
        vision = json.loads(clean)
    except json.JSONDecodeError as e:
        logger.error(f"Vision JSON parse failed: {e} | raw: {raw[:200]}")
        raise HTTPException(status_code=502, detail="Vision API returned unparseable response")

    # ── Build result ──────────────────────────────────────────
    result = {
        "job_id":               computed_job_id,
        "captured_at":          datetime.utcnow().isoformat() + "Z",
        "location": {
            "lat": str(lat) if lat else None,
            "lng": str(lng) if lng else None,
        },
        "quality":              vision.get("quality", {}),
        "work_completed":       vision.get("work_completed", []),
        "upsell":               vision.get("upsell", {}),
        "client_message_draft": vision.get("client_message_draft", ""),
        "flags":                vision.get("flags", []),
        "raw_description":      vision.get("raw_description", ""),
    }

    logger.info(
        f"photo_analyzed job={computed_job_id} "
        f"score={result['quality'].get('score')} "
        f"status={result['quality'].get('status')}"
    )
    return JSONResponse(content=result)


def _generate_job_id() -> str:
    d = datetime.utcnow()
    import random
    return f"JOB-{d.month}{str(d.day).zfill(2)}-{random.randint(1000,9999)}"
