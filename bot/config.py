from __future__ import annotations

import os
from pathlib import Path
from typing import List, Optional

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, Field, validator

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_CONFIG_PATH = BASE_DIR / "config.yaml"


class GeneralConfig(BaseModel):
  account_currency: str = "USD"
  symbols: List[str] = Field(default_factory=lambda: ["EURUSD", "GBPUSD"])
  timeframes: List[str] = Field(default_factory=lambda: ["M15", "H1"])
  poll_interval_seconds: int = 60
  heartbeat_interval_seconds: int = 15


class RiskConfig(BaseModel):
  risk_per_trade: float = Field(default=0.01, ge=0.0005, le=0.05)
  max_concurrent_trades: int = Field(default=3, ge=1, le=20)
  max_daily_drawdown: float = Field(default=0.03, ge=0.005, le=0.2)
  stop_loss_atr_multiplier: float = Field(default=1.8, ge=0.5, le=5)
  take_profit_multiple: float = Field(default=2.0, ge=1, le=6)


class MT5Config(BaseModel):
  terminal_path: Path
  server: str
  login: int
  password: str
  timezone_offset_minutes: int = 0

  @validator("terminal_path", pre=True)
  def expand_path(cls, value: str | Path) -> Path:
    return Path(str(value)).expanduser()


class GeminiConfig(BaseModel):
  model: str = Field(default_factory=lambda: os.getenv("GEMINI_MODEL", "gemini-1.5-pro"))
  prompt_template: str
  api_key: Optional[str] = Field(default_factory=lambda: os.getenv("GEMINI_API_KEY"))

  @validator("api_key", always=True)
  def api_key_required(cls, value: Optional[str]) -> str:
    if not value:
      raise ValueError(
        "Gemini API key missing. Set GEMINI_API_KEY environment variable."
      )
    return value


class StrategyConfig(BaseModel):
  general: GeneralConfig = Field(default_factory=GeneralConfig)
  risk: RiskConfig = Field(default_factory=RiskConfig)
  mt5: MT5Config
  gemini: GeminiConfig


def load_config(path: Optional[Path | str] = None) -> StrategyConfig:
  """Load structured configuration for the trading bot."""
  config_path = (
    Path(path).expanduser()
    if path
    else Path(os.getenv("BOT_CONFIG_PATH", DEFAULT_CONFIG_PATH))
  )

  if not config_path.exists():
    raise FileNotFoundError(
      f"Configuration file not found at {config_path}. "
      "Copy config.example.yaml to config.yaml and adjust credentials."
    )

  with config_path.open("r", encoding="utf-8") as fh:
    raw = yaml.safe_load(fh) or {}

  return StrategyConfig.model_validate(raw)
