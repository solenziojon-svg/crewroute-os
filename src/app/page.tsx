// src/app/api/analyze/route.ts
import { NextRequest, NextResponse } from "next/server";
import Anthropic from "@anthropic-ai/sdk";

export const runtime = "nodejs";

const anthropic = new Anthropic({
  apiKey: process.env.ANTHROPIC_API_KEY || "",
});

export async function POST(request: NextRequest) {
  try {
    if (!process.env.ANTHROPIC_API_KEY) {
      return NextResponse.json(
        { error: "ANTHROPIC_API_KEY is missing from environment variables." },
        { status: 500 }
      );
    }

    // 1. Parse Inbound Multi-part Form Data
    const formData = await request.formData();
    const file = formData.get("photo") as File | null;
    const mode = formData.get("mode") as "estimate" | "audit" | null;

    if (!file) {
      return NextResponse.json({ error: "Missing image file from device capture." }, { status: 400 });
    }
    if (!mode || (mode !== "estimate" && mode !== "audit")) {
      return NextResponse.json({ error: "Invalid operational execution mode specified." }, { status: 400 });
    }

    // 2. Extract Base64 Representation
    const bytes = await file.arrayBuffer();
    const buffer = Buffer.from(bytes);
    const base64Image = buffer.toString("base64");

    // 3. Dynamic Strategy Definitions: Prompts and Schema Definitions
    let systemPrompt = "";
    let toolDefinition: Anthropic.Messages.Tool;

    if (mode === "estimate") {
      systemPrompt = `You are the core pricing estimation vision agent for CrewRoute OS. 
Analyze the landscape site photo provided. Accurate sizing analysis is critical. Estimate the square footage of the treatment area. 
Identify the turf/ground cover type and any visible access bottlenecks (e.g. narrow gates, locked side entries). 
Classify the condition status using exactly one of these tokens: pristine, maintained, neglected, overgrown, severely_overgrown.`;

      toolDefinition = {
        name: "extract_landscape_estimate",
        description: "Record structured site metrics directly from visual property evaluations.",
        input_schema: {
          type: "object",
          properties: {
            square_footage: { type: "number", description: "Estimated square footage of the target property treatment zone." },
            turf_type: { type: "string", description: "Identified ground cover or turf breed (e.g., Bermuda Grass, Fescue, Mixed Weeds, Dirt)." },
            access_constraints: { type: "string", description: "Visible spatial gate limits, locks, or terrain hazards. Use 'None detected' if clear." },
            condition: { 
              type: "string", 
              enum: ["pristine", "maintained", "neglected", "overgrown", "severely_overgrown"],
              description: "The visual degradation status of the yard layout."
            }
          },
          required: ["square_footage", "turf_type", "access_constraints", "condition"]
        }
      };
    } else {
      systemPrompt = `You are the principal quality assurance inspector for CrewRoute OS.
Analyze the completed job photo provided to grade performance. Evaluate work accuracy against professional landscaping benchmarks.
Assign a raw quality score from 1-10, classify verification status, and construct a list of explicit work tasks completed.
Actively scan for structural upsell opportunities (e.g. mulch replenishment, tree trimming, dead plant swaps) with rough market dollar valuations.
Draft a friendly, immediate SMS update message to the client outlining site conditions and generate operator flags if work deficiencies or property damage are present.`;

      toolDefinition = {
        name: "extract_quality_audit",
        description: "Execute a structural performance quality grade and highlight upsell value channels.",
        input_schema: {
          type: "object",
          properties: {
            quality: {
              type: "object",
              properties: {
                score: { type: "number", description: "Performance execution rating from 1 to 10." },
                status: { type: "string", enum: ["verified", "requires_attention"], description: "Overall pass state identifier." },
                notes: { type: "string", description: "Detailed observations regarding the quality metrics seen." }
              },
              required: ["score", "status", "notes"]
            },
            work_completed: {
              type: "array",
              items: { type: "string" },
              description: "Individual bullet items of distinct actions executed (e.g., Perimeter Edged, Lawn Mowed, Debris Blown)."
            },
            upsell: {
              type: "object",
              properties: {
                detected: { type: "boolean", description: "True if secondary revenue vectors are noticed in background structures." },
                description: { type: "string", description: "Summary of the value-add work recommended." },
                estimated_value: { type: "number", description: "Approximate target pricing revenue for the up-sell." }
              },
              required: ["detected", "description", "estimated_value"]
            },
            client_message_draft: { type: "string", description: "Polite update message summarizing completion state for the owner." },
            flags: {
              type: "array",
              items: { type: "string" },
              description: "Operator exceptions or missed items needing remedial dispatch corrections."
            }
          },
          required: ["quality", "work_completed", "upsell", "client_message_draft", "flags"]
        }
      };
    }

    // 4. Dispatch Execution to Claude 3.5 Sonnet
    const response = await anthropic.messages.create({
      model: "claude-3-5-sonnet-20241022",
      max_tokens: 1500,
      system: systemPrompt,
      messages: [
        {
          role: "user",
          content: [
            {
              type: "image",
              source: {
                type: "base64",
                media_type: file.type as "image/jpeg" | "image/png" | "image/gif" | "image/webp",
                data: base64Image,
              },
            },
            {
              type: "text",
              text: `Execute deep evaluation of current imagery using tool constraint arguments for mode: ${mode}.`
            }
          ],
        },
      ],
      tools: [toolDefinition],
      tool_choice: { type: "tool", name: toolDefinition.name }
    });

    // 5. Structure Validation Gate
    const toolUseBlock = response.content.find((block) => block.type === "tool_use");
    if (!toolUseBlock || typeof toolUseBlock.input !== "object") {
      return NextResponse.json(
        { error: "Model failed to output standard structured data payloads." },
        { status: 502 }
      );
    }

    // Returns structural JSON matching front-end objects cleanly
    return NextResponse.json(toolUseBlock.input, { status: 200 });

  } catch (error: any) {
    console.error("Pipeline Exception Triggered:", error);
    return NextResponse.json(
      { error: error.message || "Internal visual processing pipeline error." },
      { status: 500 }
    );
  }
}
