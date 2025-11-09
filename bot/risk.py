from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from typing import Optional

import MetaTrader5 as mt5
from loguru import logger


def determine_pip_size(symbol_info: mt5.symbol_info) -> float:
  if symbol_info is None:
    raise ValueError("Symbol info not provided.")
  digits = symbol_info.digits
  if "JPY" in symbol_info.name and digits == 3:
    return 0.01
  if digits >= 4:
    return 0.0001
  return 0.01


@dataclass
class RiskManager:
  risk_per_trade: float
  max_concurrent_trades: int
  max_daily_drawdown: float
  stop_loss_atr_multiplier: float
  take_profit_multiple: float
  day_start_equity: Optional[float] = None
  last_reset: Optional[dt.date] = None
  open_positions: int = 0
  _last_equity: Optional[float] = field(default=None, init=False)

  def reset_if_new_day(self, equity: float) -> None:
    today = dt.date.today()
    if self.last_reset != today:
      self.day_start_equity = equity
      self.last_reset = today
      logger.debug("Daily risk counters reset. Equity={}", equity)

  def register_open_position(self) -> None:
    self.open_positions += 1

  def register_closed_position(self) -> None:
    self.open_positions = max(0, self.open_positions - 1)

  def check_drawdown(self, equity: float) -> bool:
    self.reset_if_new_day(equity)
    if self.day_start_equity is None:
      self.day_start_equity = equity
      return True

    drawdown = (self.day_start_equity - equity) / self.day_start_equity
    self._last_equity = equity
    if drawdown >= self.max_daily_drawdown:
      logger.warning("Daily drawdown {:.2%} breached.", drawdown)
      return False
    return True

  def can_open_trade(self, equity: float) -> bool:
    if not self.check_drawdown(equity):
      return False
    if self.open_positions >= self.max_concurrent_trades:
      logger.info(
        "Max concurrent trades reached: {}",
        self.max_concurrent_trades,
      )
      return False
    return True

  def compute_position_size(
    self,
    symbol: str,
    equity: float,
    stop_loss_pips: float,
  ) -> float:
    if stop_loss_pips <= 0:
      raise ValueError("Stop-loss pips must be positive.")

    symbol_info = mt5.symbol_info(symbol)
    if symbol_info is None:
      raise RuntimeError(f"Symbol {symbol} not available in MT5.")

    contract_size = symbol_info.trade_contract_size
    pip_size = determine_pip_size(symbol_info)
    pip_value = contract_size * pip_size

    risk_capital = equity * self.risk_per_trade
    volume = risk_capital / (stop_loss_pips * pip_value)

    # Align to allowed step
    step = symbol_info.volume_step or 0.01
    min_lot = symbol_info.volume_min or step
    max_lot = symbol_info.volume_max or 100.0

    lots = max(min_lot, min(max_lot, round(volume / step) * step))
    logger.debug(
      "Position sizing for {} | equity={} risk={} stop={} -> lots={}",
      symbol,
      equity,
      self.risk_per_trade,
      stop_loss_pips,
      lots,
    )
    return lots
