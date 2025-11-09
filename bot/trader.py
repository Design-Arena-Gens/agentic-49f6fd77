from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import MetaTrader5 as mt5
from loguru import logger

from bot.config import StrategyConfig
from bot.gemini import GeminiAdvisor
from bot.mt5_client import MT5Credentials, MetaTraderGateway
from bot.risk import RiskManager
from bot.strategy import StrategyEngine, TradePlan


@dataclass
class BotState:
  running: bool = False
  last_heartbeat: Optional[float] = None
  active_symbol: Optional[str] = None
  open_positions: int = 0
  account_balance: float = 0.0
  account_equity: float = 0.0
  today_pnl: float = 0.0
  risk_per_trade: float = 0.01
  max_concurrent_trades: int = 3
  max_daily_drawdown: float = 0.03
  recent_signals: List[Dict] = field(default_factory=list)
  notes: List[str] = field(default_factory=list)

  def snapshot(self) -> Dict:
    return {
      "running": self.running,
      "lastHeartbeat": (
        time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(self.last_heartbeat))
        if self.last_heartbeat
        else None
      ),
      "activeSymbol": self.active_symbol,
      "openPositions": self.open_positions,
      "accountBalance": self.account_balance,
      "accountEquity": self.account_equity,
      "todayPnL": self.today_pnl,
      "riskPerTrade": self.risk_per_trade,
      "maxConcurrentTrades": self.max_concurrent_trades,
      "maxDailyDrawdown": self.max_daily_drawdown,
      "recentSignals": self.recent_signals[-10:][::-1],
      "notes": self.notes[-10:][::-1],
    }


class TradingBot:
  def __init__(self, config: StrategyConfig) -> None:
    self.config = config
    creds = MT5Credentials(
      terminal_path=str(config.mt5.terminal_path),
      server=config.mt5.server,
      login=config.mt5.login,
      password=config.mt5.password,
      timezone_offset_minutes=config.mt5.timezone_offset_minutes,
    )

    self.gateway = MetaTraderGateway(creds)
    self.risk_manager = RiskManager(**config.risk.model_dump())
    self.advisor = GeminiAdvisor(
      api_key=config.gemini.api_key,
      model=config.gemini.model,
      prompt_template=config.gemini.prompt_template,
    )
    self.strategy = StrategyEngine(self.gateway, self.advisor, self.risk_manager)
    self.state = BotState(
      risk_per_trade=config.risk.risk_per_trade,
      max_concurrent_trades=config.risk.max_concurrent_trades,
      max_daily_drawdown=config.risk.max_daily_drawdown,
    )
    self._lock = threading.Lock()
    self._worker: Optional[threading.Thread] = None
    self._stop_event = threading.Event()

  def _update_account_snapshot(self) -> None:
    info = self.gateway.account_info()
    self.state.account_balance = info["balance"]
    self.state.account_equity = info["equity"]
    self.state.today_pnl = info["profit"]
    self.state.last_heartbeat = time.time()
    positions = self.gateway.open_positions()
    self.state.open_positions = len(positions)
    self.risk_manager.open_positions = len(positions)

  def _append_note(self, message: str) -> None:
    self.state.notes.append(message)
    self.state.notes = self.state.notes[-60:]

  def _append_signal(self, plan: TradePlan) -> None:
    self.state.recent_signals.append(
      {
        "id": str(time.time()),
        "symbol": plan.symbol,
        "direction": plan.direction,
        "confidence": plan.confidence,
        "reason": plan.rationale,
        "createdAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
      }
    )
    self.state.recent_signals = self.state.recent_signals[-60:]

  def _positions_for_symbol(self, symbol: str) -> List:
    positions = self.gateway.open_positions()
    return [pos for pos in positions if pos["symbol"] == symbol]

  def _execute_plan(self, plan: TradePlan) -> None:
    tick = self.gateway.current_tick(plan.symbol)
    if tick is None:
      self._append_note(f"No tick data for {plan.symbol}; skipping execution.")
      return

    price = tick["ask"] if plan.direction == "BUY" else tick["bid"]
    action = mt5.ORDER_TYPE_BUY if plan.direction == "BUY" else mt5.ORDER_TYPE_SELL
    ticket = self.gateway.place_order(
      symbol=plan.symbol,
      action=action,
      volume=plan.volume,
      price=price,
      sl=plan.sl,
      tp=plan.tp,
      comment=f"Gemini FX Autopilot | {plan.rationale[:48]}",
    )
    self._append_note(f"Executed {plan.direction} {plan.symbol} #{ticket}")
    self._append_signal(plan)
    self.risk_manager.register_open_position()

  def _process_symbol(self, symbol: str) -> None:
    positions = self._positions_for_symbol(symbol)
    equity = self.state.account_equity or self.state.account_balance
    timeframe = self.config.general.timeframes[0]

    if positions:
      logger.debug("Existing positions on {}. Skipping new entries.", symbol)
      return

    plan = self.strategy.build_signal(symbol, timeframe, equity)
    if plan:
      self._execute_plan(plan)
      self.state.active_symbol = plan.symbol

  def _loop(self) -> None:
    logger.info("Trading loop started.")
    heartbeat_interval = self.config.general.heartbeat_interval_seconds
    poll_interval = self.config.general.poll_interval_seconds

    while not self._stop_event.is_set():
      with self._lock:
        try:
          self._update_account_snapshot()
          for symbol in self.config.general.symbols:
            self._process_symbol(symbol)
        except Exception as exc:
          logger.exception("Processing cycle failed: {}", exc)
          self._append_note(f"Cycle exception: {exc}")
      time.sleep(poll_interval)
      self.state.last_heartbeat = time.time()
      time.sleep(max(0, heartbeat_interval - poll_interval))

    logger.info("Trading loop stopped.")

  def start(self) -> None:
    if self.state.running:
      return
    self.gateway.bootstrap()
    self._stop_event.clear()
    self._worker = threading.Thread(target=self._loop, daemon=True)
    self._worker.start()
    self.state.running = True
    self._append_note("Bot started.")

  def stop(self) -> None:
    if not self.state.running:
      return
    self._stop_event.set()
    if self._worker:
      self._worker.join(timeout=5)
    self.state.running = False
    self.gateway.shutdown()
    self._append_note("Bot stopped.")

  def status(self) -> Dict:
    with self._lock:
      return self.state.snapshot()

  def update_risk(
    self,
    risk_per_trade: float,
    max_concurrent_trades: int,
    max_daily_drawdown: float,
  ) -> Dict:
    with self._lock:
      self.risk_manager.risk_per_trade = risk_per_trade
      self.risk_manager.max_concurrent_trades = max_concurrent_trades
      self.risk_manager.max_daily_drawdown = max_daily_drawdown
      self.state.risk_per_trade = risk_per_trade
      self.state.max_concurrent_trades = max_concurrent_trades
      self.state.max_daily_drawdown = max_daily_drawdown
      self._append_note(
        f"Risk updated | risk={risk_per_trade:.2%}, slots={max_concurrent_trades}, dd={max_daily_drawdown:.1%}"
      )
      return self.state.snapshot()
