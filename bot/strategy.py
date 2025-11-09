from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import MetaTrader5 as mt5
import numpy as np
import pandas as pd
from loguru import logger

from bot.gemini import Decision, GeminiAdvisor
from bot.mt5_client import MetaTraderGateway
from bot.risk import RiskManager


@dataclass
class TradePlan:
  symbol: str
  direction: Decision
  confidence: float
  sl: float
  tp: float
  volume: float
  rationale: str


def compute_atr(data: pd.DataFrame, period: int = 14) -> float:
  high_low = data["high"] - data["low"]
  high_close = np.abs(data["high"] - data["close"].shift())
  low_close = np.abs(data["low"] - data["close"].shift())
  ranges = pd.concat([high_low, high_close, low_close], axis=1)
  true_range = np.max(ranges, axis=1)
  atr = true_range.rolling(window=period).mean().iloc[-1]
  return float(atr)


def compute_rsi(series: pd.Series, period: int = 14) -> float:
  delta = series.diff()
  gain = delta.clip(lower=0)
  loss = -delta.clip(upper=0)
  avg_gain = gain.rolling(window=period).mean()
  avg_loss = loss.rolling(window=period).mean()
  rs = avg_gain / avg_loss
  rsi = 100 - (100 / (1 + rs))
  return float(rsi.iloc[-1])


class StrategyEngine:
  def __init__(
    self,
    gateway: MetaTraderGateway,
    advisor: GeminiAdvisor,
    risk_manager: RiskManager,
  ) -> None:
    self.gateway = gateway
    self.advisor = advisor
    self.risk = risk_manager

  def build_signal(
    self,
    symbol: str,
    timeframe: str,
    equity: float,
  ) -> Optional[TradePlan]:
    rates = self.gateway.symbol_rates(symbol, timeframe, bars=300)
    atr = compute_atr(rates)
    rsi = compute_rsi(rates["close"])

    technical_summary = (
      f"ATR({timeframe})={atr:.5f}, RSI({timeframe})={rsi:.2f}, "
      f"Close={rates['close'].iloc[-1]:.5f}, Trend={np.sign(rates['close'].diff().tail(10).sum())}"
    )

    sentiment_notes = (
      "Risk sentiment neutral. Monitor central bank rhetoric and USD index bias."
    )

    ohlcv_snapshot = (
      rates.tail(50)[["time", "open", "high", "low", "close", "tick_volume"]]
      .assign(time=lambda df: df["time"].astype(str))
      .to_dict(orient="records")
    )

    signal = self.advisor.analyse(
      symbol=symbol,
      timeframe=timeframe,
      ohlcv_snapshot={"data": ohlcv_snapshot},
      sentiment_notes=sentiment_notes,
      technical_summary=technical_summary,
    )

    logger.info("Gemini suggests {} {} (confidence {:.0%})", symbol, signal.decision, signal.confidence)

    if signal.decision == "FLAT" or signal.confidence < 0.6:
      return None

    if not self.risk.can_open_trade(equity):
      logger.info("Risk constraints prevent new {} trade.", symbol)
      return None

    tick = self.gateway.current_tick(symbol)
    if tick is None:
      return None

    price = tick["ask"] if signal.decision == "BUY" else tick["bid"]
    stop_pips = signal.stop_loss_pips
    take_pips = signal.take_profit_pips
    symbol_info = mt5.symbol_info(symbol)

    point = symbol_info.point if symbol_info else 0.0001
    sl = price - stop_pips * point if signal.decision == "BUY" else price + stop_pips * point
    tp = price + take_pips * point if signal.decision == "BUY" else price - take_pips * point

    volume = self.risk.compute_position_size(symbol, equity, stop_pips)

    return TradePlan(
      symbol=symbol,
      direction=signal.decision,
      confidence=signal.confidence,
      sl=sl,
      tp=tp,
      volume=volume,
      rationale=signal.rationale,
    )
