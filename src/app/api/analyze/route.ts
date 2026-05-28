import { NextRequest, NextResponse } from 'next/server';

export async function POST(request: NextRequest) {
  return NextResponse.json({ 
    message: "API route is working",
    squareFootage: 2500,
    estimatedPrice: 4200,
    confidenceScore: 85,
    detectedFeatures: ["grass", "trees"],
    notes: "Test response - backend connected"
  });
}