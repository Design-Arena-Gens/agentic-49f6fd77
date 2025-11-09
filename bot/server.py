from __future__ import annotations

import argparse
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
from pydantic import BaseModel
import uvicorn

from bot.config import load_config
from bot.trader import TradingBot

app = FastAPI(title="Gemini FX Autopilot API", version="0.1.0")
app.add_middleware(
  CORSMiddleware,
  allow_origins=["*"],
  allow_credentials=True,
  allow_methods=["*"],
  allow_headers=["*"],
)

bot: TradingBot | None = None


class ControlPayload(BaseModel):
  action: str


class RiskPayload(BaseModel):
  riskPerTrade: float
  maxConcurrentTrades: int
  maxDailyDrawdown: float


@app.on_event("startup")
async def startup_event() -> None:
  global bot
  config = load_config()
  bot = TradingBot(config)
  logger.info("Bot ready. Use /control to start trading.")


@app.get("/status")
async def status() -> dict:
  if bot is None:
    raise HTTPException(status_code=500, detail="Bot not initialized.")
  return bot.status()


@app.post("/control")
async def control(payload: ControlPayload) -> dict:
  if bot is None:
    raise HTTPException(status_code=500, detail="Bot not initialized.")

  action = payload.action.lower()
  if action == "start":
    bot.start()
  elif action == "stop":
    bot.stop()
  elif action == "refresh":
    pass
  else:
    raise HTTPException(status_code=400, detail="Unknown action.")

  return bot.status()


@app.post("/config")
async def update_config(payload: RiskPayload) -> dict:
  if bot is None:
    raise HTTPException(status_code=500, detail="Bot not initialized.")
  return bot.update_risk(
    risk_per_trade=payload.riskPerTrade,
    max_concurrent_trades=payload.maxConcurrentTrades,
    max_daily_drawdown=payload.maxDailyDrawdown,
  )


def main() -> None:
  parser = argparse.ArgumentParser(description="Run Gemini FX Autopilot API server.")
  parser.add_argument(
    "--config",
    type=Path,
    default=None,
    help="Path to configuration YAML file.",
  )
  parser.add_argument("--host", default="0.0.0.0")
  parser.add_argument("--port", type=int, default=8000)
  args = parser.parse_args()

  if args.config:
    # Override default path through env var
    args.config = args.config.expanduser().resolve()
    logger.info("Loading configuration: {}", args.config)
    os.environ["BOT_CONFIG_PATH"] = str(args.config)
    load_config(args.config)

  uvicorn.run("bot.server:app", host=args.host, port=args.port, reload=False)


if __name__ == "__main__":
  main()
