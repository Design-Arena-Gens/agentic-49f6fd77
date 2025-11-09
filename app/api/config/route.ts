import { NextResponse } from "next/server";
import { updateRiskControls } from "@/lib/agentClient";

export const dynamic = "force-dynamic";

export async function POST(request: Request) {
  try {
    const body = await request.json();
    const { riskPerTrade, maxConcurrentTrades, maxDailyDrawdown } = body ?? {};

    if (
      typeof riskPerTrade !== "number" ||
      typeof maxConcurrentTrades !== "number" ||
      typeof maxDailyDrawdown !== "number"
    ) {
      return NextResponse.json(
        { error: "Risk configuration payload invalid." },
        { status: 400 }
      );
    }

    const status = await updateRiskControls({
      riskPerTrade,
      maxConcurrentTrades,
      maxDailyDrawdown,
    });

    return NextResponse.json(status);
  } catch (error) {
    return NextResponse.json(
      {
        error:
          error instanceof Error
            ? error.message
            : "Failed to update risk controls",
      },
      { status: 502 }
    );
  }
}
