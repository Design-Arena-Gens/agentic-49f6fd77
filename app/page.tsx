"use client";

import { useEffect, useMemo, useState } from "react";

type BotStatus = {
  running: boolean;
  lastHeartbeat: string | null;
  activeSymbol: string | null;
  openPositions: number;
  accountBalance: number;
  accountEquity: number;
  todayPnL: number;
  riskPerTrade: number;
  maxConcurrentTrades: number;
  maxDailyDrawdown: number;
  recentSignals: Array<{
    id: string;
    symbol: string;
    direction: "BUY" | "SELL";
    confidence: number;
    reason: string;
    createdAt: string;
  }>;
  notes: string[];
};

const DEFAULT_STATUS: BotStatus = {
  running: false,
  lastHeartbeat: null,
  activeSymbol: null,
  openPositions: 0,
  accountBalance: 0,
  accountEquity: 0,
  todayPnL: 0,
  riskPerTrade: 0.01,
  maxConcurrentTrades: 3,
  maxDailyDrawdown: 0.03,
  recentSignals: [],
  notes: [],
};

export default function Home() {
  const [status, setStatus] = useState<BotStatus>(DEFAULT_STATUS);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const heartbeatAge = useMemo(() => {
    if (!status.lastHeartbeat) return "No heartbeat yet";
    const diff = Date.now() - new Date(status.lastHeartbeat).getTime();
    if (diff < 60_000) return "Live";
    const minutes = Math.round(diff / 60_000);
    return `${minutes}m ago`;
  }, [status.lastHeartbeat]);

  useEffect(() => {
    let mounted = true;
    async function fetchStatus() {
      try {
        setError(null);
        const response = await fetch("/api/status", { cache: "no-store" });
        if (!response.ok) {
          throw new Error(`Status ${response.status}`);
        }
        const data = (await response.json()) as BotStatus;
        if (mounted) {
          setStatus({ ...DEFAULT_STATUS, ...data });
          setLoading(false);
        }
      } catch (err) {
        if (!mounted) return;
        setError(err instanceof Error ? err.message : "Failed to load status");
        setLoading(false);
      }
    }

    fetchStatus();
    const interval = setInterval(fetchStatus, 15_000);
    return () => {
      mounted = false;
      clearInterval(interval);
    };
  }, []);

  async function handleControl(action: "start" | "stop" | "refresh") {
    try {
      setSaving(true);
      setError(null);
      const response = await fetch("/api/control", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action }),
      });
      if (!response.ok) throw new Error(`Control ${response.status}`);
      const data = (await response.json()) as BotStatus;
      setStatus({ ...DEFAULT_STATUS, ...data });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to issue command");
    } finally {
      setSaving(false);
    }
  }

  async function handleRiskUpdate(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    try {
      setSaving(true);
      setError(null);
      const response = await fetch("/api/config", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          riskPerTrade: Number(form.get("riskPerTrade")) / 100,
          maxConcurrentTrades: Number(form.get("maxConcurrentTrades")),
          maxDailyDrawdown: Number(form.get("maxDailyDrawdown")) / 100,
        }),
      });
      if (!response.ok) throw new Error(`Config ${response.status}`);
      const data = (await response.json()) as BotStatus;
      setStatus({ ...DEFAULT_STATUS, ...data });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update risk");
    } finally {
      setSaving(false);
    }
  }

  const statusColor = status.running ? "#10b981" : "#f97316";
  const statusText = status.running ? "Bot Active" : "Bot Idle";

  return (
    <main className="page">
      <header className="hero">
        <div>
          <h1>Gemini FX Autopilot</h1>
          <p>Autonomous Gemini-powered execution layer for MetaTrader 5.</p>
        </div>
        <div className="status-card" style={{ borderColor: statusColor }}>
          <span className="dot" style={{ backgroundColor: statusColor }} />
          <div>
            <strong>{statusText}</strong>
            <small>Heartbeat: {heartbeatAge}</small>
          </div>
        </div>
      </header>

      {error && <p className="error">Error: {error}</p>}

      <section className="grid">
        <article className="card">
          <header className="card-header">
            <h2>Account Snapshot</h2>
            <button onClick={() => handleControl("refresh")} disabled={saving}>
              Refresh
            </button>
          </header>
          <div className="metrics">
            <Metric
              label="Balance"
              value={`$${status.accountBalance.toFixed(2)}`}
            />
            <Metric
              label="Equity"
              value={`$${status.accountEquity.toFixed(2)}`}
            />
            <Metric
              label="Open Positions"
              value={status.openPositions.toString()}
            />
            <Metric
              label="Active Symbol"
              value={status.activeSymbol ?? "—"}
            />
            <Metric
              label="Today's PnL"
              value={`${status.todayPnL >= 0 ? "+" : "-"}$${Math.abs(
                status.todayPnL
              ).toFixed(2)}`}
              valueClass={status.todayPnL >= 0 ? "positive" : "negative"}
            />
          </div>
          <footer className="card-footer">
            <button
              onClick={() => handleControl(status.running ? "stop" : "start")}
              className={status.running ? "stop" : "start"}
              disabled={saving}
            >
              {status.running ? "Pause Bot" : "Resume Bot"}
            </button>
          </footer>
        </article>

        <article className="card">
          <header className="card-header">
            <h2>Risk Controls</h2>
          </header>
          <form className="form" onSubmit={handleRiskUpdate}>
            <label>
              Risk per Trade (%)
              <input
                name="riskPerTrade"
                type="number"
                min="0.1"
                max="5"
                step="0.1"
                defaultValue={status.riskPerTrade * 100}
              />
            </label>
            <label>
              Max Concurrent Trades
              <input
                name="maxConcurrentTrades"
                type="number"
                min="1"
                max="10"
                step="1"
                defaultValue={status.maxConcurrentTrades}
              />
            </label>
            <label>
              Max Daily Drawdown (%)
              <input
                name="maxDailyDrawdown"
                type="number"
                min="1"
                max="20"
                step="0.5"
                defaultValue={status.maxDailyDrawdown * 100}
              />
            </label>
            <button type="submit" disabled={saving}>
              Update Controls
            </button>
          </form>
        </article>

        <article className="card signals">
          <header className="card-header">
            <h2>Signal Feed</h2>
          </header>
          <div className="timeline">
            {loading && <p>Loading signals…</p>}
            {!loading && status.recentSignals.length === 0 && (
              <p>No signals yet.</p>
            )}
            {status.recentSignals.map((signal) => (
              <div key={signal.id} className="timeline-item">
                <div className="timeline-meta">
                  <span className={`badge ${signal.direction.toLowerCase()}`}>
                    {signal.direction}
                  </span>
                  <span className="confidence">
                    {(signal.confidence * 100).toFixed(0)}% confidence
                  </span>
                  <span>
                    {new Date(signal.createdAt).toLocaleString(undefined, {
                      hour: "2-digit",
                      minute: "2-digit",
                      month: "short",
                      day: "2-digit",
                    })}
                  </span>
                </div>
                <h3>{signal.symbol}</h3>
                <p>{signal.reason}</p>
              </div>
            ))}
          </div>
        </article>

        <article className="card notes">
          <header className="card-header">
            <h2>AI Advisory Feed</h2>
          </header>
          <ul>
            {status.notes.length === 0 && <li>No advisories yet.</li>}
            {status.notes.map((note, index) => (
              <li key={index}>{note}</li>
            ))}
          </ul>
        </article>
      </section>
    </main>
  );
}

function Metric({
  label,
  value,
  valueClass,
}: {
  label: string;
  value: string;
  valueClass?: "positive" | "negative";
}) {
  return (
    <div className="metric">
      <span>{label}</span>
      <strong className={valueClass}>{value}</strong>
    </div>
  );
}
