# Gemini FX Autopilot

Autonomous forex execution stack combining a Vercel-ready Next.js cockpit with a Windows-based MetaTrader 5 agent powered by Gemini AI research.

- **Front-end**: Next.js 14 (App Router) dashboard for control, telemetry, and advisory feeds.
- **Agent**: Python service that launches MetaTrader 5, streams market context to Gemini, computes trade plans, manages risk, and executes trades.

## Contents

- `app/` – Next.js UI and API routes (deployable to Vercel).
- `lib/` – Shared front-end utilities for agent communication.
- `bot/` – Gemini/MetaTrader 5 automation core and FastAPI bridge.

## Front-end (Vercel)

```bash
npm install
npm run dev         # local dashboard on http://localhost:3000
npm run build       # production build
npm start           # production server
```

Environment variables:

```
AGENT_API_BASE_URL=<http://windows-host:8000>
GEMINI_MODEL=gemini-1.5-flash
```

- `AGENT_API_BASE_URL` should point to the Windows host running the Python agent (defaults to in-memory mock if unspecified).

## MT5 + Gemini Agent (Windows)

Prerequisites:

- Windows machine with MetaTrader 5 installed (terminal at `G:\Program Files\terminal64\terminal64.exe` by default).
- Python 3.11+
- Valid Gemini API key (`GEMINI_API_KEY`).

Setup:

```bash
cd bot
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy config.example.yaml config.yaml  # then edit credentials
set GEMINI_API_KEY=<your_key>
python -m bot.server --host 0.0.0.0 --port 8000
```

Endpoints exposed to the dashboard:

- `GET /status` – health, equity, open positions, AI notes.
- `POST /control` – `{ "action": "start" | "stop" | "refresh" }`.
- `POST /config` – update risk controls on the fly.

## Safety & Risk Controls

- ATR-based sizing with configurable stop/take-profit ratios.
- Equity/risk checks (`risk_per_trade`, `max_concurrent_trades`, `max_daily_drawdown`).
- Daily reset of drawdown counters.

## Deployment

1. Deploy the front-end to Vercel (`vercel deploy --prod --yes --token $VERCEL_TOKEN --name agentic-49f6fd77`).
2. Run the Python agent on the MT5 workstation with firewall rules allowing Vercel to reach port 8000 (or tunnel via a secure channel).
3. Set `AGENT_API_BASE_URL` on Vercel to the reachable URL of the agent.

## Disclaimer

Live trading involves risk. Review, extend, and test thoroughly before enabling on funded accounts. Configure broker credentials, symbols, and risk parameters carefully to match your trading profile.
