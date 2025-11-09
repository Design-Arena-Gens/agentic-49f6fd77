import { NextResponse } from "next/server";
import { fetchBotStatus } from "@/lib/agentClient";

export const dynamic = "force-dynamic";

export async function GET() {
  try {
    const status = await fetchBotStatus();
    return NextResponse.json(status);
  } catch (error) {
    return NextResponse.json(
      {
        error: error instanceof Error ? error.message : "Failed to fetch status",
      },
      { status: 502 }
    );
  }
}
