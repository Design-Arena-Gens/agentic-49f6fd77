import { NextResponse } from "next/server";
import { sendControlCommand } from "@/lib/agentClient";

export const dynamic = "force-dynamic";

export async function POST(request: Request) {
  try {
    const body = await request.json();
    const action = body?.action;

    if (!["start", "stop", "refresh"].includes(action)) {
      return NextResponse.json(
        { error: "Invalid action." },
        { status: 400 }
      );
    }

    const status = await sendControlCommand(action);
    return NextResponse.json(status);
  } catch (error) {
    return NextResponse.json(
      {
        error:
          error instanceof Error
            ? error.message
            : "Failed to relay control command",
      },
      { status: 502 }
    );
  }
}
