import { NextRequest, NextResponse } from 'next/server';
import Anthropic from '@anthropic-ai/sdk';

const client = new Anthropic({
  apiKey: process.env.ANTHROPIC_API_KEY,
});

const SYSTEM_PROMPT = `You are CrewRoute AI, the estimating engine for CJS Landscape Solutions 
in Pacific Beach, San Diego. You analyze property photos to produce structured landscaping estimates.

You must respond with ONLY a valid JSON object — no markdown, no explanation, no preamble.

Analyze the image and return exactly this structure:
{
  "squareFootage": <integer, estimated turf/landscape area in sq ft>,
  "condition": <"maintained" | "overgrown" | "neglected">,
  "obstruction": <"none" | "minor" | "significant">,
  "description": <string, 2-3 sentences: what you see, access notes, crew considerations>,
  "detectedFeatures": <array of strings>,
  "upsellOpportunities": <array of {service: string, value: number}>,
  "estimatedPrice": <integer, calculated price in USD>,
  "confidenceScore": <integer 0-100>,
  "crewNotes": <string, specific instructions for the crew arriving on site>
}

Pricing logic to apply:
- Base rate: $0.14/sq ft for maintained properties
- Overgrown: multiply by 1.4
- Neglected: multiply by 1.8  
- Obstruction surcharge: +$45 per zone with significant access issues
- Minimum job: $85
- Round to nearest $5

Be conservative on square footage — err toward underestimating rather than overestimating.
Flag anything that would require a site visit before committing to a price.`;

export async function POST(request: NextRequest) {
  const apiKey = process.env.ANTHROPIC_API_KEY;
  if (!apiKey) {
    return NextResponse.json(
      { error: 'ANTHROPIC_API_KEY not configured' },
      { status: 500 }
    );
  }

  try {
    const body = await request.json();
    const { image, filename } = body;

    if (!image) {
      return NextResponse.json(
        { error: 'No image provided' },
        { status: 400 }
      );
    }

    const mediaType = filename?.toLowerCase().endsWith('.png')
      ? 'image/png'
      : 'image/jpeg';

    const message = await client.messages.create({
      model: 'claude-3-5-sonnet-20241022',
      max_tokens: 1024,
      system: SYSTEM_PROMPT,
      messages: [
        {
          role: 'user',
          content: [
            {
              type: 'image',
              source: {
                type: 'base64',
                media_type: mediaType,
                data: image,
              },
            },
            {
              type: 'text',
              text: 'Analyze this property photo and return the JSON estimate.',
            },
          ],
        },
      ],
    });

    const rawText = message.content
      .filter((block) => block.type === 'text')
      .map((block) => (block as { type: 'text'; text: string }).text)
      .join('');

    const clean = rawText.replace(/```json|```/g, '').trim();
    const result = JSON.parse(clean);

    return NextResponse.json({
      ...result,
      analyzedAt: new Date().toISOString(),
      filename: filename || 'property-photo.jpg',
      model: 'claude-3-5-sonnet-20241022',
    });

  } catch (error) {
    console.error('Analyze API error:', error);

    return NextResponse.json({
      squareFootage: 2450,
      condition: 'maintained',
      obstruction: 'none',
      description: 'Demo fallback: Claude Vision unavailable. Check ANTHROPIC_API_KEY in Vercel env vars.',
      detectedFeatures: ['demo mode'],
      upsellOpportunities: [],
      estimatedPrice: 385,
      confidenceScore: 0,
      crewNotes: 'DEMO DATA — not a real estimate.',
      analyzedAt: new Date().toISOString(),
      filename: 'demo',
      model: 'fallback',
    }, { status: 200 });
  }
}
