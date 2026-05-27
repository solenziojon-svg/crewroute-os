// analyze-photo.js
import config from '../config.js';

export default async function handler(req, res) {
  if (req.method !== "POST") {
    return res.status(405).json({ error: "Method not allowed" });
  }

  try {
    const { image, mediaType = "image/jpeg" } = req.body;

    if (!image) {
      return res.status(400).json({ error: "No image provided" });
    }

    const response = await fetch("https://api.anthropic.com/v1/messages", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "x-api-key": config.anthropicApiKey,
        "anthropic-version": "2023-06-01"
      },
      body: JSON.stringify({
        model: "claude-3-5-sonnet-20241022",
        max_tokens: 700,
        messages: [{
          role: "user",
          content: [
            {
              type: "image",
              source: {
                type: "base64",
                media_type: mediaType,
                data: image
              }
            },
            {
              type: "text",
              text: "You are a professional landscaping job auditor. Analyze this photo and return ONLY valid JSON with these exact fields: quality (score 1-10, status, notes), work_completed (array), upsell (detected, description, estimated_value), raw_description, square_footage, condition, and obstruction."
            }
          ]
        }]
      })
    });

    if (!response.ok) {
      throw new Error("Claude Vision API failed");
    }

    const data = await response.json();
    const text = data.content?.[0]?.text || "{}";

    let result;
    try {
      result = JSON.parse(text.replace(/```json|```/g, "").trim());
    } catch {
      result = { error: "Failed to parse Claude response" };
    }

    res.status(200).json(result);

  } catch (error) {
    console.error(error);
    res.status(500).json({ error: "Analysis failed", message: error.message });
  }
}