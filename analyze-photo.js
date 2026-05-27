/**
 * api/analyze-photo.js — Vercel Serverless Function
 * ──────────────────────────────────────────────────
 * Drop this file into your project's /api folder.
 * Vercel auto-routes POST /api/analyze-photo to this handler.
 *
 * Env var required in Vercel dashboard:
 *   ANTHROPIC_API_KEY=sk-ant-...
 *
 * Accepts: multipart/form-data with fields:
 *   photo     (File)             — the yard image
 *   job_id    (string, optional)
 *   lat/lng   (number, optional)
 *
 * Returns: structured JSON job payload (same schema as FastAPI route)
 */

import Anthropic from "@anthropic-ai/sdk";
import formidable from "formidable";
import fs from "fs";
import path from "path";

export const config = { api: { bodyParser: false } };

const VISION_PROMPT = `You are a professional landscaping job quality auditor.
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
}`;

function generateJobId() {
  const d = new Date();
  const rand = Math.floor(Math.random() * 9000) + 1000;
  return `JOB-${d.getMonth()+1}${String(d.getDate()).padStart(2,"0")}-${rand}`;
}

export default async function handler(req, res) {
  if (req.method !== "POST") {
    return res.status(405).json({ error: "Method not allowed" });
  }

  if (!process.env.ANTHROPIC_API_KEY) {
    return res.status(500).json({ error: "ANTHROPIC_API_KEY not configured" });
  }

  // ── Parse multipart form ────────────────────────────────────
  const form = formidable({ maxFileSize: 10 * 1024 * 1024 }); // 10MB
  let fields, files;
  try {
    [fields, files] = await form.parse(req);
  } catch (err) {
    return res.status(400).json({ error: "Invalid form data: " + err.message });
  }

  const photoFile = files.photo?.[0];
  if (!photoFile) {
    return res.status(400).json({ error: "No photo provided" });
  }

  const photoBytes  = fs.readFileSync(photoFile.filepath);
  const base64Img   = photoBytes.toString("base64");
  const mediaType   = photoFile.mimetype || "image/jpeg";
  const jobId       = fields.job_id?.[0] || generateJobId();
  const lat         = fields.lat?.[0] || null;
  const lng         = fields.lng?.[0] || null;

  // ── Call Claude Vision ──────────────────────────────────────
  const client = new Anthropic({ apiKey: process.env.ANTHROPIC_API_KEY });

  let vision;
  try {
    const message = await client.messages.create({
      model:      "claude-sonnet-4-20250514",
      max_tokens: 1000,
      messages: [{
        role: "user",
        content: [
          {
            type:   "image",
            source: { type: "base64", media_type: mediaType, data: base64Img }
          },
          { type: "text", text: VISION_PROMPT }
        ]
      }]
    });

    const raw   = message.content?.[0]?.text || "";
    const clean = raw.replace(/```json\n?/g,"").replace(/```\n?/g,"").trim();
    vision = JSON.parse(clean);

  } catch (err) {
    console.error("Claude API error:", err.message);
    return res.status(502).json({ error: "Vision API failed: " + err.message });
  } finally {
    // Clean up temp file
    try { fs.unlinkSync(photoFile.filepath); } catch {}
  }

  // ── Return result ───────────────────────────────────────────
  return res.status(200).json({
    job_id:               jobId,
    captured_at:          new Date().toISOString(),
    location:             { lat, lng },
    quality:              vision.quality              || {},
    work_completed:       vision.work_completed       || [],
    upsell:               vision.upsell               || {},
    client_message_draft: vision.client_message_draft || "",
    flags:                vision.flags                || [],
    raw_description:      vision.raw_description      || "",
  });
}
