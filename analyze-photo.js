// analyze-photo.js
export default async function handler(req, res) {
  if (req.method !== 'POST') {
    return res.status(405).json({ error: 'Only POST allowed' });
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
        "x-api-key": process.env.ANTHROPIC_API_KEY,
        "anthropic-version": "2023-06-01"
      },
      body: JSON.stringify({
        model: "claude-3-5-sonnet-20241022",
        max_tokens: 800,
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
              text: "Analyze this landscaping job photo. Return only valid JSON with: quality score (1-10), work_completed (array), upsell opportunities, and a short description."
            }
          ]
        }]
      })
    });

    if (!response.ok) throw new Error("Claude API failed");

    const data = await response.json();
    const text = data.content?.[0]?.text || "{}";
    
    let result;
    try {
      result = JSON.parse(text.replace(/```json|```/g, '').trim());
    } catch {
      result = { error: "Failed to parse response" };
    }

    res.status(200).json(result);

  } catch (err) {
    console.error(err);
    res.status(500).json({ error: "Analysis failed", message: err.message });
  }
}