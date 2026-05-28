import { NextRequest, NextResponse } from 'next/server';

interface EstimateResult {
  squareFootage: number;
  detectedFeatures: string[];
  estimatedPrice: number;
  confidenceScore: number;
  notes: string;
}

export async function POST(request: NextRequest) {
  try {
    const formData = await request.formData();
    const photo = formData.get('photo') as File | null;

    if (!photo) {
      return NextResponse.json(
        { error: 'No photo provided' },
        { status: 400 }
      );
    }

    // Convert image to base64
    const bytes = await photo.arrayBuffer();
    const base64Image = Buffer.from(bytes).toString('base64');
    const mimeType = photo.type || 'image/jpeg';

    // Call Claude Vision
    const anthropicResponse = await fetch('https://api.anthropic.com/v1/messages', {
      method: 'POST',
      headers: {
        'x-api-key': process.env.ANTHROPIC_API_KEY!,
        'anthropic-version': '2023-06-01',
        'content-type': 'application/json',
      },
      body: JSON.stringify({
        model: 'claude-3-5-sonnet-20241022',
        max_tokens: 1200,
        temperature: 0,
        system: `You are an expert landscaping field estimator for CrewRoute OS.
Analyze the property photo and return ONLY valid JSON with these exact keys:
{
  "squareFootage": number (estimated maintainable area in sqft),
  "detectedFeatures": string[] (e.g. ["overgrown brush", "retaining wall", "pavers", "slope"]),
  "confidenceScore": number (0-100),
  "notes": string (brief professional assessment)
}`,
        messages: [
          {
            role: 'user',
            content: [
              {
                type: 'image',
                source: {
                  type: 'base64',
                  media_type: mimeType,
                  data: base64Image,
                },
              },
              {
                type: 'text',
                text: 'Analyze this property photo and return the structured JSON estimate.',
              },
            ],
          },
        ],
      }),
    });

    if (!anthropicResponse.ok) {
      const errorText = await anthropicResponse.text();
      throw new Error(`Claude Vision failed: ${errorText}`);
    }

    const anthropicData = await anthropicResponse.json();
    const rawText = anthropicData.content?.[0]?.text?.trim();

    // Parse and clean JSON response
    let parsed: any;
    try {
      const cleaned = rawText.replace(/```json|```/g, '').trim();
      parsed = JSON.parse(cleaned);
    } catch (parseError) {
      console.error('Failed to parse Claude response:', rawText);
      throw new Error('Claude returned invalid JSON');
    }

    // Apply CrewRoute pricing logic
    const sqft = parsed.squareFootage || 0;
    const baseHours = sqft / 1600;
    const laborCost = baseHours * 65;
    const estimatedPrice = Math.round(laborCost / (1 - 0.35));

    const result: EstimateResult = {
      squareFootage: sqft,
      detectedFeatures: parsed.detectedFeatures || [],
      estimatedPrice: estimatedPrice,
      confidenceScore: Math.round((parsed.confidenceScore || 0.75) * 100),
      notes: parsed.notes || 'Analysis completed successfully.',
    };

    return NextResponse.json(result);

  } catch (error: any) {
    console.error('Analysis error:', error);
    return NextResponse.json(
      { error: error.message || 'Analysis failed' },
      { status: 500 }
    );
  }
}