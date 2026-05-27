// analyze-photo.js
import config from '../config.js';

export default async function handler(req, res) {
  if (req.method !== "POST") {
    return res.status(405).json({ error: "Method not allowed" });
  }

  try {
    const { image } = req.body;

    if (!image) {
      return res.status(400).json({ error: "No image provided" });
    }

    // For now, return a simple response so we know it works
    const result = {
      success: true,
      message: "Photo received successfully",
      square_footage: 6500,
      condition: "maintained",
      quality_score: 8,
      note: "This is a test response. Real Claude Vision coming next."
    };

    res.status(200).json(result);

  } catch (error) {
    res.status(500).json({ error: "Server error", message: error.message });
  }
}