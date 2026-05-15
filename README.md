# QB AI Agent — CFO Intelligence Platform

An AI-powered CFO dashboard that connects to **QuickBooks Online** for 4 LLCs, powered by **Claude claude-sonnet-4-6**, served via **FastAPI + Docker**, and exposed publicly through a **Cloudflare Tunnel**.

---

## What it does

| Feature | Details |
|---|---|
| 💬 **CFO AI Chat** | Ask natural-language questions about any company's finances. Claude uses 16 QBO tools (P&L, cash flow, invoices, AR/AP, vendors, accounts…). Streaming SSE responses. |
| 📊 **CFO Dashboard** | Live multi-company snapshot — Revenue, Net Income, Margin, Cash. Month-status strip showing which months are closed vs open, uncategorized transaction count. |
| 📋 **Executive Report** | CEO-facing view with monthly trend charts (Chart.js), EOY forecast (run-rate), company deep-dives, accounting health scorecard, and IRS deadline tracker. |
| 🗂 **iOS-inspired UI** | Shared sidebar navigation, Apple dark-mode design system, ChatGPT-style chat interface. |
| 📅 **IRS Tax Calendar** | 35+ 2025–2026 deadlines (941, 940, 1065, 1120-S, 1120, Schedule C, W-2/1099). Mark done per company. |
| 🔐 **QBO OAuth** | Production OAuth 2.0 with auto token refresh, tokens stored in Supabase. |

---

## Architecture

```
Browser → Cloudflare Tunnel (qb.asmtech.cloud)
           → Docker: FastAPI (port 8000)
              ├── app/main.py          FastAPI routes + /api/executive
              ├── app/agent.py         Claude tool loop (16 QBO tools)
              ├── app/qbo_client.py    QBO REST client, token refresh
              ├── app/db.py            Supabase helpers
              ├── app/irs_calendar.py  Tax deadline calendar
              ├── static/index.html    Chat UI (ChatGPT-style)
              ├── static/dashboard.html CFO multi-company dashboard
              ├── static/executive.html CEO executive report
              └── static/sidebar.js   Shared iOS design system + sidebar
```

---

## Companies

Defined in `app/main.py → COMPANY_LIST`:

```python
COMPANY_LIST = [
    {"name": "Miami Image Society LLC",  "env": "production"},
    {"name": "Lush Media Group LLC",     "env": "production"},
    {"name": "ASM Tech Media Group LLC", "env": "production"},
    {"name": "Atomick LLC",              "env": "production"},
]
```

---

## Prerequisites

| Requirement | Notes |
|---|---|
| Docker Desktop | Running locally |
| Supabase project | Free tier works |
| Intuit Developer account | **Production** app (not sandbox) |
| Cloudflare account | Zero Trust tunnel, custom domain |
| Anthropic API key | claude-sonnet-4-6 |

---

## Setup

### 1 — Clone and configure

```bash
git clone https://github.com/ASM-TECH-MIAMI/quickbooks_app.git
cd quickbooks_app
cp .env.example .env
# Fill in .env with your real values (see sections below)
```

### 2 — Supabase database

Run the migration in Supabase SQL editor:

```bash
# Open supabase/migrations/20260513000000_initial.sql
# Paste into Supabase → SQL Editor → Run
```

Tables created: `companies`, `conversations`, `deadline_status`

### 3 — Intuit QuickBooks Online app

1. Go to https://developer.intuit.com → **My Apps** → your production app
2. Add redirect URI: `https://YOUR-DOMAIN/auth/callback`
3. Copy **Client ID** and **Client Secret** into `.env`

### 4 — Cloudflare Tunnel

```bash
# In Cloudflare Zero Trust → Access → Tunnels:
# 1. Create tunnel → copy the token into .env as CLOUDFLARE_TUNNEL_TOKEN
# 2. Add public hostname: your-domain.com → localhost:8000
```

### 5 — Build and run

```bash
docker compose up --build -d
docker logs quickbooks-app-1 -f   # watch for "Application startup complete"
```

### 6 — Connect each company (OAuth)

Visit each URL once — it will redirect to Intuit and store tokens in Supabase:

```
https://YOUR-DOMAIN/auth/connect/1   → Miami Image Society LLC
https://YOUR-DOMAIN/auth/connect/2   → Lush Media Group LLC
https://YOUR-DOMAIN/auth/connect/3   → ASM Tech Media Group LLC
https://YOUR-DOMAIN/auth/connect/4   → Atomick LLC
```

---

## Environment variables

| Variable | Where to get it |
|---|---|
| `QB_CLIENT_ID` | Intuit Developer → My Apps → Production tab |
| `QB_CLIENT_SECRET` | Same |
| `ANTHROPIC_API_KEY` | https://console.anthropic.com |
| `SUPABASE_URL` | Supabase → Project Settings → API |
| `SUPABASE_KEY` | Supabase → Project Settings → API → anon/public |
| `DATABASE_URL` | Supabase → Project Settings → Database → URI |
| `APP_BASE_URL` | Your public domain, e.g. `https://qb.asmtech.cloud` |
| `CLOUDFLARE_TUNNEL_TOKEN` | CF Zero Trust → Tunnels → your tunnel → token |

---

## API endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/` | Chat UI |
| `GET` | `/dashboard` | CFO Dashboard |
| `GET` | `/executive` | CEO Executive Report |
| `GET` | `/api/companies` | List connected companies |
| `POST` | `/api/chat` | Stream AI response (SSE) |
| `GET` | `/api/dashboard` | Multi-company snapshot JSON |
| `GET` | `/api/executive` | Full executive report JSON |
| `GET` | `/api/deadlines` | IRS deadlines per company |
| `POST` | `/api/deadlines/{id}/status` | Mark deadline done/na/pending |
| `GET` | `/auth/connect/{1-4}` | Start QBO OAuth for company N |
| `GET` | `/auth/callback` | QBO OAuth callback |

---

## Useful commands

```bash
# Rebuild after code changes
docker compose down && docker compose up --build -d

# View live logs
docker logs quickbooks-app-1 -f

# Check connected companies in Supabase
# Supabase → Table Editor → companies

# Hot reload (no rebuild needed for static/ and app/ changes)
# Volumes in docker-compose.yml mount ./app and ./static live
```

---

## Tech stack

- **Backend**: Python 3.12, FastAPI, Uvicorn
- **AI**: Anthropic `claude-sonnet-4-6`, tool use agentic loop
- **Database**: Supabase (PostgreSQL)
- **QBO**: Intuit REST API v3, OAuth 2.0, minor version 65
- **Frontend**: Vanilla JS, Tailwind CDN, Chart.js
- **Infrastructure**: Docker, Cloudflare Tunnel
