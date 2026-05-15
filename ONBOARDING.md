# QB AI Agent — Claude Code Onboarding

Welcome. This is the **QB AI CFO Platform** — a FastAPI web app that connects to 4 QuickBooks Online companies and provides an AI CFO chat, multi-company dashboard, and CEO executive report.

## Quick orientation (read this first)

- **Owner**: ASM Tech Media Group / Michel Zarate
- **Repo**: https://github.com/ASM-TECH-MIAMI/quickbooks_app
- **Live URL**: https://qb.asmtech.cloud
- **Local port**: 8000 (Docker)
- **Stack**: Python 3.12, FastAPI, Claude claude-sonnet-4-6, Supabase, Docker, Cloudflare Tunnel

## The 4 companies

| # | Company | OAuth connect URL |
|---|---|---|
| 1 | Miami Image Society LLC | `/auth/connect/1` |
| 2 | Lush Media Group LLC | `/auth/connect/2` |
| 3 | ASM Tech Media Group LLC | `/auth/connect/3` |
| 4 | Atomick LLC | `/auth/connect/4` |

All tokens stored in Supabase `companies` table. Auto-refresh on every API call.

## Key files to know

```
app/main.py          ← All FastAPI routes. START HERE for backend changes.
app/agent.py         ← 16 QBO tools + Claude agentic loop. Add new tools here.
app/qbo_client.py    ← QBO REST client (token refresh, report helpers, queries).
app/db.py            ← Supabase CRUD helpers.
app/irs_calendar.py  ← IRS tax deadlines 2025–2026. Add new deadlines here.
static/sidebar.js    ← SHARED: injects iOS design system CSS + sidebar HTML into every page.
static/index.html    ← Chat UI (ChatGPT style).
static/dashboard.html← CFO multi-company dashboard.
static/executive.html← CEO executive report with charts.
docker-compose.yml   ← app + cloudflared services. Volumes mount ./app and ./static live.
.env                 ← Secrets. NEVER commit. See .env.example for keys needed.
supabase/migrations/ ← Database schema SQL.
```

## Environment secrets needed

Create `.env` from `.env.example`. Required keys:
- `QB_CLIENT_ID` / `QB_CLIENT_SECRET` — Intuit production app
- `ANTHROPIC_API_KEY` — Claude API
- `SUPABASE_URL` / `SUPABASE_KEY` / `DATABASE_URL` — Supabase project
- `APP_BASE_URL` — e.g. `https://qb.asmtech.cloud`
- `CLOUDFLARE_TUNNEL_TOKEN` — CF Zero Trust tunnel token

## How to run locally

```bash
cp .env.example .env
# Fill in .env values
docker compose up --build -d
# App at http://localhost:8000
```

## Common tasks

### Add a new QBO tool to the AI agent
1. Open `app/agent.py`
2. Add to `TOOLS` list (follow the Anthropic tool schema)
3. Add handler in `dispatch_tool_sync()`
4. Add helper method in `app/qbo_client.py` if needed

### Add a new page/route
1. Add FastAPI route in `app/main.py` (serve HTML)
2. Create `static/your-page.html`
3. Call `QB.init({ active:'your-page' })` at bottom of page script (sidebar auto-injects)

### Add a new IRS deadline
Open `app/irs_calendar.py` → add entry to `DEADLINES_2025` or `DEADLINES_2026` list.

### Re-connect a company after token expiry
Visit `https://qb.asmtech.cloud/auth/connect/N` (1–4) and complete OAuth.

### Rebuild after backend changes
```bash
docker compose down && docker compose up --build -d
docker logs quickbooks-app-1 -f
```

### Hot reload (no rebuild needed)
`./app/` and `./static/` are mounted as Docker volumes — changes to Python files and HTML/JS take effect on next request (uvicorn auto-reloads Python, static files served directly).

## Design system

All styling lives in `static/sidebar.js` — it injects a `<style>` tag with CSS variables and a `<div class="sidebar">` into every page. Pages should NOT have their own nav bars.

Key CSS variables:
```css
--s1: #09090B     /* page background */
--s2: #1C1C1E     /* card surface */
--blue: #0A84FF   /* iOS blue */
--green: #30D158  /* iOS green */
--red: #FF453A    /* iOS red */
--orange: #FF9F0A /* iOS orange */
--purple: #BF5AF2 /* iOS purple */
```

Badge classes: `.badge.b-green`, `.b-orange`, `.b-red`, `.b-blue`, `.b-purple`
Color text: `.c-green`, `.c-red`, `.c-orange`, `.c-blue`, `.c-dim`
Section label: `.sec-label`

## API data shapes

### GET /api/dashboard
```json
{
  "companies": [{ "name", "revenue", "net_income", "margin_pct", "cash", "month_status": [...] }],
  "deadlines": [...],
  "overdue": [...],
  "as_of": "2025-05-14"
}
```

### GET /api/executive
```json
{
  "portfolio": { "total_revenue_ytd", "total_net_income_ytd", "forecast_revenue_eoy", ... },
  "companies": [{ "name", "ytd": {...}, "monthly": [...], "forecast": {...}, "accounting": {...} }],
  "monthly_actual": [{ "month", "revenue", "net_income", "gross_profit" }],
  "monthly_projected": [{ "month", "revenue", "net_income", "projected": true }],
  "accounting_summary": { "avg_health_score", "total_months_open", "max_days_behind" },
  "deadlines": [...],
  "overdue": [...]
}
```

### POST /api/chat
```json
// Request
{ "company_name": "Miami Image Society LLC", "message": "What is our YTD revenue?", "conversation_id": null }
// Response: SSE stream of events: conv_id, tool_start, tool_done, message, done
```

## Supabase schema

| Table | Purpose |
|---|---|
| `companies` | One row per connected QBO company. Stores realm_id, access_token, refresh_token. |
| `conversations` | Chat history as JSONB messages array. |
| `deadline_status` | Per-company deadline tracking (done/pending/na + notes). |

## Known issues / gotchas

- **BookCloseDate**: QBO returns this from `CompanyInfo`. If `null`, all past months show as "open". Accountant must set it in QBO → Company Settings → Advanced → Close the books.
- **Monthly P&L current month**: The `summarize_column_by=Month` QBO report may show $0 for the current partial month. YTD totals are correct.
- **Token expiry**: QBO access tokens expire after 1 hour. Refresh tokens last 100 days. If refresh token expires, OAuth must be redone for that company.
- **ASM Tech Media Group**: Not yet connected (as of May 2025). Use `/auth/connect/3`.
- **MINOR_VERSION**: QBO API calls use `minorversion=65`. Do not lower this.
