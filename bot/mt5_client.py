from __future__ import annotations

import subprocess
import sys
import time
from dataclasses import dataclass
from typing import Dict, List, Optional

import MetaTrader5 as mt5
import pandas as pd
from loguru import logger

TIMEFRAME_MAP: Dict[str, int] = {
  "M1": mt5.TIMEFRAME_M1,
  "M5": mt5.TIMEFRAME_M5,
  "M15": mt5.TIMEFRAME_M15,
  "M30": mt5.TIMEFRAME_M30,
  "H1": mt5.TIMEFRAME_H1,
  "H4": mt5.TIMEFRAME_H4,
  "D1": mt5.TIMEFRAME_D1,
}


@dataclass
class MT5Credentials:
  terminal_path: str
  server: str
  login: int
  password: str
  timezone_offset_minutes: int = 0


class MetaTraderGateway:
  def __init__(self, creds: MT5Credentials) -> None:
    self.creds = creds
    self.initialized = False

  def bootstrap(self) -> None:
    """Ensure the MetaTrader terminal is running and authenticated."""
    if not mt5.initialize():
      logger.info("Launching MetaTrader 5 terminal: {}", self.creds.terminal_path)
      try:
        subprocess.Popen(
          [self.creds.terminal_path],
          stdout=subprocess.DEVNULL,
          stderr=subprocess.DEVNULL,
        )
      except FileNotFoundError as exc:
        logger.error("MT5 terminal not found: {}", exc)
        raise
      time.sleep(5)
      if not mt5.initialize():
        raise RuntimeError("Failed to initialize MetaTrader5 after launching terminal.")

    authorized = mt5.login(
      self.creds.login, password=self.creds.password, server=self.creds.server
    )
    if not authorized:
      raise RuntimeError(f"MetaTrader5 login failed: {mt5.last_error()}")

    self.initialized = True
    logger.success("Connected to MT5 account {}", self.creds.login)

  def shutdown(self) -> None:
    mt5.shutdown()
    self.initialized = False

  def ensure_initialized(self) -> None:
    if not self.initialized:
      self.bootstrap()

  def account_info(self) -> Dict[str, float]:
    self.ensure_initialized()
    info = mt5.account_info()._asdict()
    return {
      "balance": float(info["balance"]),
      "equity": float(info["equity"]),
      "margin": float(info["margin"]),
      "currency": info["currency"],
      "profit": float(info["profit"]),
    }

  def open_positions(self) -> List[Dict[str, float]]:
    self.ensure_initialized()
    positions = mt5.positions_get()
    result: List[Dict[str, float]] = []
    if positions:
      for pos in positions:
        data = pos._asdict()
        result.append(
          {
            "ticket": data["ticket"],
            "symbol": data["symbol"],
            "type": data["type"],
            "volume": data["volume"],
            "price_open": data["price_open"],
            "sl": data["sl"],
            "tp": data["tp"],
            "profit": data["profit"],
          }
        )
    return result

  def symbol_rates(self, symbol: str, timeframe: str, bars: int = 250) -> pd.DataFrame:
    self.ensure_initialized()
    mt_timeframe = TIMEFRAME_MAP.get(timeframe.upper())
    if not mt_timeframe:
      raise ValueError(f"Unsupported timeframe {timeframe}.")

    rates = mt5.copy_rates_from_pos(symbol, mt_timeframe, 0, bars)
    if rates is None:
      raise RuntimeError(f"Failed to fetch rates for {symbol}: {mt5.last_error()}")
    frame = pd.DataFrame(rates)
    frame["time"] = pd.to_datetime(frame["time"], unit="s")
    return frame

  def current_tick(self, symbol: str) -> Optional[Dict[str, float]]:
    self.ensure_initialized()
    tick = mt5.symbol_info_tick(symbol)
    if tick is None:
      return None
    data = tick._asdict()
    return {
      "bid": data["bid"],
      "ask": data["ask"],
      "last": data["last"],
      "time": data["time"],
    }

  def place_order(
    self,
    symbol: str,
    action: int,
    volume: float,
    price: float,
    sl: float,
    tp: float,
    comment: str,
  ) -> int:
    self.ensure_initialized()
    request = {
      "action": mt5.TRADE_ACTION_DEAL,
      "symbol": symbol,
      "volume": volume,
      "type": action,
      "price": price,
      "sl": sl,
      "tp": tp,
      "deviation": 15,
      "magic": 424242,
      "comment": comment,
      "type_time": mt5.ORDER_TIME_GTC,
      "type_filling": mt5.ORDER_FILLING_IOC,
    }

    logger.info("Sending order {} {}", symbol, "BUY" if action == mt5.ORDER_TYPE_BUY else "SELL")
    result = mt5.order_send(request)
    if result is None:
      last_error = mt5.last_error()
      logger.error("order_send returned None: {}", last_error)
      raise RuntimeError(f"Order send failed: {last_error}")

    if result.retcode != mt5.TRADE_RETCODE_DONE:
      logger.error("Order rejected: {} {}", result.retcode, result.comment)
      raise RuntimeError(f"Order rejected: {result.retcode} {result.comment}")

    logger.success("Order executed. Ticket {}", result.order)
    return result.order
