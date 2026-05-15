"""
QB AI Agent — FastAPI web server
Routes:
  GET  /                        → chat UI
  GET  /api/companies           → list connected companies
  POST /api/chat                → send message, stream agent response
  GET  /api/deadlines           → upcoming IRS deadlines
  POST /api/deadlines/{id}/done → mark deadline done
  GET  /auth/connect/{index}    → start QBO OAuth (1-4)
  GET  /auth/callback           → QBO OAuth callback
"""

import calendar
import json
import os
import secrets
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, timedelta
from pathlib import Path
from typing import AsyncGenerator, Optional

import anthropic
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .agent import TOOLS, dispatch_tool_sync, SYSTEM_PROMPT
from .db import (
    list_companies,
    get_company,
    upsert_company,
    update_tokens,
    create_conversation,
    get_conversation,
    append_message,
    get_deadline_statuses,
    set_deadline_status,
)
from .irs_calendar import get_upcoming_deadlines, get_overdue_deadlines
from .qbo_client import QBOClient

# ── Constants ──────────────────────────────────────────────────────────────────
AUTH_URL    = "https://appcenter.intuit.com/connect/oauth2"
TOKEN_URL   = "https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer"
SCOPES      = "com.intuit.quickbooks.accounting"

COMPANY_LIST = [
    {"name": "Miami Image Society LLC",  "env": "production"},
    {"name": "Lush Media Group LLC",      "env": "production"},
    {"name": "ASM Tech Media Group LLC",  "env": "production"},
    {"name": "Atomick LLC",               "env": "production"},
]

app = FastAPI(title="QB AI Agent")

# Mount static files (the chat UI)
static_dir = Path(__file__).parent.parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# In-memory OAuth state store (short-lived, restart-safe)
_oauth_states: dict[str, dict] = {}


# ── Models ─────────────────────────────────────────────────────────────────────
class ChatRequest(BaseModel):
    company_name: str
    message: str
    conversation_id: Optional[str] = None


class DeadlineStatusRequest(BaseModel):
    company_name: str
    status: str      # "done" | "pending" | "na"
    notes: str = ""


# ── Root ───────────────────────────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
async def root():
    index = static_dir / "index.html"
    return HTMLResponse(index.read_text())


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page():
    return HTMLResponse((static_dir / "dashboard.html").read_text())


@app.get("/executive", response_class=HTMLResponse)
async def executive_page():
    return HTMLResponse((static_dir / "executive.html").read_text())


# ── Companies ──────────────────────────────────────────────────────────────────
@app.get("/api/companies")
async def api_companies():
    return {"companies": list_companies()}


# ── Chat (streaming SSE) ───────────────────────────────────────────────────────
@app.post("/api/chat")
async def api_chat(req: ChatRequest):
    company = get_company(req.company_name)
    if not company:
        raise HTTPException(404, f"Company '{req.company_name}' not connected.")

    qbo = QBOClient.from_db(company)
    ai  = anthropic.Anthropic()
    system = SYSTEM_PROMPT.format(
        today=date.today().isoformat(),
        company=req.company_name,
    )

    # Load or create conversation
    conv_id = req.conversation_id
    if conv_id:
        conv = get_conversation(conv_id)
        messages = conv["messages"] if conv else []
    else:
        conv_id = create_conversation(company["id"])
        messages = []

    messages.append({"role": "user", "content": req.message})

    async def stream() -> AsyncGenerator[str, None]:
        nonlocal messages

        def sse(event: str, data: dict) -> str:
            return f"event: {event}\ndata: {json.dumps(data)}\n\n"

        yield sse("conv_id", {"id": conv_id})

        while True:
            response = ai.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=4096,
                system=system,
                tools=TOOLS,
                messages=messages,
            )
            assistant_content = response.content
            messages.append({"role": "assistant", "content": [
                {"type": b.type, **({"text": b.text} if hasattr(b, "text") else
                                    {"name": b.name, "id": b.id, "input": b.input} if b.type == "tool_use" else {})}
                for b in assistant_content
            ]})

            if response.stop_reason == "end_turn":
                for block in assistant_content:
                    if hasattr(block, "text"):
                        yield sse("message", {"text": block.text})
                break

            elif response.stop_reason == "tool_use":
                tool_results = []
                for block in assistant_content:
                    if block.type == "tool_use":
                        yield sse("tool_start", {"name": block.name})
                        try:
                            result = dispatch_tool_sync(block.name, block.input, qbo)
                            result_str = json.dumps(result, default=str)
                            yield sse("tool_done", {"name": block.name, "ok": True})
                        except Exception as exc:
                            result_str = json.dumps({"error": str(exc)})
                            yield sse("tool_done", {"name": block.name, "ok": False, "error": str(exc)})

                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": result_str,
                        })

                messages.append({"role": "user", "content": tool_results})
            else:
                break

        # Persist conversation
        append_message(conv_id, messages)
        yield sse("done", {})

    return StreamingResponse(stream(), media_type="text/event-stream")


# ── IRS Deadlines ──────────────────────────────────────────────────────────────
@app.get("/api/deadlines")
async def api_deadlines(company_name: str, within_days: int = 90):
    company = get_company(company_name)
    company_id = company["id"] if company else None

    upcoming = get_upcoming_deadlines(within_days=within_days)
    overdue  = get_overdue_deadlines()

    statuses: dict = {}
    if company_id:
        statuses = get_deadline_statuses(company_id)

    def enrich(d: dict) -> dict:
        s = statuses.get(d["id"], {})
        return {**d, "status": s.get("status", "pending"), "notes": s.get("notes", "")}

    return {
        "upcoming": [enrich(d) for d in upcoming],
        "overdue":  [enrich(d) for d in overdue],
    }


@app.post("/api/deadlines/{deadline_id}/status")
async def api_deadline_status(deadline_id: str, req: DeadlineStatusRequest):
    company = get_company(req.company_name)
    if not company:
        raise HTTPException(404, "Company not found.")
    set_deadline_status(company["id"], deadline_id, req.status, req.notes)
    return {"ok": True}


# ── Month status helpers ───────────────────────────────────────────────────────
def _get_book_close_date(qbo) -> Optional[date]:
    """Return the BookCloseDate from QBO CompanyInfo, or None."""
    try:
        info = qbo.company_info()
        close_str = info.get("CompanyInfo", {}).get("BookCloseDate", "")
        if close_str:
            return date.fromisoformat(close_str[:10])
    except Exception:
        pass
    return None


def _count_uncategorized(qbo, start_str: str, end_str: str) -> int:
    """
    Count transactions posted to uncategorized / ask-my-accountant accounts
    in the given date range.  Returns -1 on error.
    """
    target_names = {
        "uncategorized expense",
        "uncategorized income",
        "uncategorized asset",
        "ask my accountant",
    }
    total = 0
    try:
        # Purchases (credit-card charges, checks, etc.)
        r = qbo.query(
            f"SELECT * FROM Purchase "
            f"WHERE TxnDate >= '{start_str}' AND TxnDate <= '{end_str}' "
            f"MAXRESULTS 1000"
        )
        for txn in r.get("Purchase", []):
            for line in txn.get("Line", []):
                acct = (
                    line.get("AccountBasedExpenseLineDetail", {})
                    .get("AccountRef", {})
                    .get("name", "")
                    .lower()
                    .strip()
                )
                if acct in target_names:
                    total += 1
                    break          # count the *transaction* once
    except Exception:
        return -1

    try:
        # Journal entries
        r = qbo.query(
            f"SELECT * FROM JournalEntry "
            f"WHERE TxnDate >= '{start_str}' AND TxnDate <= '{end_str}' "
            f"MAXRESULTS 1000"
        )
        for txn in r.get("JournalEntry", []):
            hit = False
            for line in txn.get("Line", []):
                acct = (
                    line.get("JournalEntryLineDetail", {})
                    .get("AccountRef", {})
                    .get("name", "")
                    .lower()
                    .strip()
                )
                if acct in target_names:
                    hit = True
                    break
            if hit:
                total += 1
    except Exception:
        pass

    return total


def _fetch_month_status(qbo, today: date) -> list:
    """
    Return a list of dicts for each month Jan→current, e.g.
      [{"month": 1, "name": "Jan", "status": "closed", "uncategorized": 0}, ...]
    status values: "closed" | "open" | "current"
    """
    close_date = _get_book_close_date(qbo)

    months = []
    for m in range(1, today.month + 1):
        _, last_day = calendar.monthrange(today.year, m)
        m_start = date(today.year, m, 1)
        m_end   = date(today.year, m, last_day)
        name    = m_start.strftime("%b")

        if close_date and m_end <= close_date:
            status = "closed"
            uncategorized = 0
        elif m == today.month:
            status = "current"
            uncategorized = _count_uncategorized(
                qbo, m_start.isoformat(), today.isoformat()
            )
        else:
            status = "open"
            uncategorized = _count_uncategorized(
                qbo, m_start.isoformat(), m_end.isoformat()
            )

        months.append({
            "month":        m,
            "name":         name,
            "status":       status,
            "uncategorized": uncategorized,
        })

    return months


# ── Shared P&L parsers ────────────────────────────────────────────────────────
def collect_summaries(rows_list: list) -> dict:
    """Recursively collect all Summary rows from a QBO P&L into {label: value}."""
    result = {}
    for r in rows_list:
        if isinstance(r, dict):
            summ = r.get("Summary", {}).get("ColData", [])
            if len(summ) > 1:
                label = summ[0].get("value", "").strip().lower()
                try:
                    result[label] = float(summ[1].get("value", 0) or 0)
                except (ValueError, TypeError):
                    pass
            sub = r.get("Rows", {}).get("Row", [])
            if sub:
                result.update(collect_summaries(sub))
    return result


def parse_monthly_pl(report: dict) -> list:
    """
    Parse a ProfitAndLoss report fetched with summarize_column_by=Month.
    Returns [{"month": "Jan", "revenue": x, "gross_profit": x, "net_income": x}, ...]
    """
    columns = report.get("Columns", {}).get("Column", [])

    # Build col_index → "Jan" mapping (skip index 0 = label, skip "Total")
    month_map: dict[int, str] = {}
    for i, col in enumerate(columns):
        title = col.get("ColTitle", "").strip()
        if i > 0 and title and title.lower() != "total":
            month_map[i] = title.split(" ")[0]   # "Jan 2025" → "Jan"

    monthly: dict[str, dict] = {
        name: {"month": name, "revenue": 0.0, "gross_profit": 0.0, "net_income": 0.0}
        for name in month_map.values()
    }

    TARGET = {
        "total income":  "revenue",
        "total revenue": "revenue",
        "gross profit":  "gross_profit",
        "net income":    "net_income",
        "net profit":    "net_income",
    }

    def _walk(rows_list: list):
        for r in rows_list:
            if not isinstance(r, dict):
                continue
            summ_data = r.get("Summary", {}).get("ColData", [])
            if summ_data:
                label = summ_data[0].get("value", "").strip().lower()
                for key, field in TARGET.items():
                    if key in label:
                        for idx, mname in month_map.items():
                            if idx < len(summ_data):
                                try:
                                    monthly[mname][field] = float(
                                        summ_data[idx].get("value", 0) or 0
                                    )
                                except (ValueError, TypeError):
                                    pass
                        break
            _walk(r.get("Rows", {}).get("Row", []))

    _walk(report.get("Rows", {}).get("Row", []))
    return list(monthly.values())


def _extract_cash(cf_report: dict) -> float:
    """Pull ending cash balance from a QBO CashFlow report."""
    for cr in cf_report.get("Rows", {}).get("Row", []):
        if cr.get("type") == "Section":
            summ = cr.get("Summary", {}).get("ColData", [])
            lbl  = summ[0].get("value", "").lower() if summ else ""
            if "ending" in lbl or "end" in lbl:
                try:
                    return float(summ[1]["value"])
                except Exception:
                    pass
    return 0.0


# ── CFO Dashboard — multi-company snapshot ────────────────────────────────────
def _fetch_company_snapshot(row: dict) -> dict:
    """Fetch P&L + cash for one company. Runs in a thread."""
    name = row["name"]
    try:
        qbo = QBOClient.from_db(row)
        today = date.today()
        yr_start = f"{today.year}-01-01"
        yr_end   = today.isoformat()

        pl  = qbo.profit_and_loss(yr_start, yr_end)
        cf  = qbo.cash_flow(yr_start, yr_end)

        rows = pl.get("Rows", {}).get("Row", [])
        summaries = collect_summaries(rows)

        revenue     = next((v for k, v in summaries.items() if "total income" in k or ("total" in k and "revenue" in k)), 0)
        gross_profit = summaries.get("gross profit", 0)
        net_income  = next((v for k, v in summaries.items() if "net income" in k or "net profit" in k), 0)

        cash = _extract_cash(cf)

        margin = round((net_income / revenue * 100), 1) if revenue else 0

        # Month status (closed vs open, uncategorized count)
        try:
            month_status = _fetch_month_status(qbo, today)
        except Exception:
            month_status = []

        return {
            "name":         name,
            "revenue":      revenue,
            "gross_profit": gross_profit,
            "net_income":   net_income,
            "margin_pct":   margin,
            "cash":         cash,
            "period":       f"YTD {today.year}",
            "month_status": month_status,
            "error":        None,
        }
    except Exception as e:
        return {"name": name, "error": str(e)}


@app.get("/api/dashboard")
async def api_dashboard():
    companies = list_companies()
    if not companies:
        return {"companies": [], "deadlines": [], "overdue": []}

    snapshots = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {}
        for c in companies:
            row = get_company(c["name"])
            if row:
                futures[pool.submit(_fetch_company_snapshot, row)] = c["name"]
        for future in as_completed(futures):
            snapshots.append(future.result())

    snapshots.sort(key=lambda x: -(x.get("revenue") or 0))

    upcoming = get_upcoming_deadlines(within_days=60)
    overdue  = get_overdue_deadlines()

    return {
        "companies": snapshots,
        "deadlines": upcoming[:8],
        "overdue":   overdue[:5],
        "as_of":     date.today().isoformat(),
    }


# ── Executive Report — per-company deep fetch ─────────────────────────────────
def _fetch_executive_company(row: dict, today: date, months_elapsed: float) -> dict:
    """Full executive snapshot: YTD + monthly breakdown + forecast + accounting health."""
    name = row["name"]
    try:
        qbo = QBOClient.from_db(row)
        yr       = today.year
        yr_start = f"{yr}-01-01"
        yr_end   = today.isoformat()

        # ── YTD financials ────────────────────────────────────────────────────
        pl_ytd = qbo.profit_and_loss(yr_start, yr_end)
        cf_ytd = qbo.cash_flow(yr_start, yr_end)

        summaries    = collect_summaries(pl_ytd.get("Rows", {}).get("Row", []))
        revenue      = next((v for k, v in summaries.items()
                             if "total income" in k or ("total" in k and "revenue" in k)), 0.0)
        gross_profit = summaries.get("gross profit", 0.0)
        net_income   = next((v for k, v in summaries.items()
                             if "net income" in k or "net profit" in k), 0.0)
        margin       = round(net_income / revenue * 100, 1) if revenue else 0.0
        cash         = _extract_cash(cf_ytd)

        # ── Monthly P&L (one API call, all months) ────────────────────────────
        pl_monthly_raw = qbo.get(
            "reports/ProfitAndLoss",
            {"start_date": yr_start, "end_date": yr_end,
             "summarize_column_by": "Month", "minorversion": 65},
        )
        monthly = parse_monthly_pl(pl_monthly_raw)

        # ── Forecast (linear run-rate) ─────────────────────────────────────────
        months_remaining = 12.0 - months_elapsed
        avg_rev = revenue / months_elapsed if months_elapsed else 0
        avg_inc = net_income / months_elapsed if months_elapsed else 0
        forecast_rev = round(revenue + avg_rev * months_remaining)
        forecast_inc = round(net_income + avg_inc * months_remaining)

        # ── Accounting health ─────────────────────────────────────────────────
        month_status = _fetch_month_status(qbo, today)

        past_months      = [m for m in month_status if m["status"] != "current"]
        months_closed    = sum(1 for m in past_months if m["status"] == "closed")
        months_open      = sum(1 for m in past_months if m["status"] == "open")
        total_uncat      = sum(m["uncategorized"] for m in month_status
                               if m.get("uncategorized", 0) > 0)

        # Days behind: oldest unclosed past month → expected close date was +15 days
        days_behind = 0
        for m in month_status:
            if m["status"] == "open":
                _, last_day = calendar.monthrange(yr, m["month"])
                expected_close = date(yr, m["month"], last_day) + timedelta(days=15)
                lag = (today - expected_close).days
                if lag > days_behind:
                    days_behind = max(0, lag)

        # Health score 0-100
        n_past = len(past_months)
        close_pts  = round(months_closed / n_past * 60) if n_past else 60
        uncat_pts  = max(0, 40 - total_uncat * 3)
        health     = close_pts + uncat_pts

        if months_open == 0 and total_uncat == 0:
            acct_status = "on_track"
        elif months_open <= 1 and total_uncat < 5:
            acct_status = "slightly_behind"
        elif months_open <= 2 or total_uncat < 15:
            acct_status = "behind"
        else:
            acct_status = "critical"

        return {
            "name": name,
            "ytd": {
                "revenue":      revenue,
                "gross_profit": gross_profit,
                "net_income":   net_income,
                "margin_pct":   margin,
                "cash":         cash,
            },
            "monthly": monthly,
            "forecast": {
                "revenue_eoy":    forecast_rev,
                "net_income_eoy": forecast_inc,
                "margin_eoy":     round(forecast_inc / forecast_rev * 100, 1) if forecast_rev else 0,
            },
            "accounting": {
                "months_closed":   months_closed,
                "months_open":     months_open,
                "total_uncat":     total_uncat,
                "days_behind":     days_behind,
                "health_score":    health,
                "status":          acct_status,
            },
            "month_status": month_status,
            "error":        None,
        }
    except Exception as e:
        return {"name": name, "error": str(e)}


@app.get("/api/executive")
async def api_executive():
    """Full CFO → CEO executive report with monthly breakdown and forecasts."""
    companies = list_companies()
    if not companies:
        return {"companies": [], "portfolio": {}, "monthly_portfolio": []}

    today   = date.today()
    yr      = today.year
    _, d_in_mo = calendar.monthrange(yr, today.month)
    months_elapsed   = (today.month - 1) + today.day / d_in_mo
    months_remaining = 12.0 - months_elapsed

    results: list[dict] = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {
            pool.submit(_fetch_executive_company, get_company(c["name"]), today, months_elapsed): c["name"]
            for c in companies if get_company(c["name"])
        }
        for fut in as_completed(futures):
            results.append(fut.result())

    results.sort(key=lambda x: -(x.get("ytd", {}).get("revenue") or 0))

    valid = [r for r in results if not r.get("error")]

    # ── Portfolio totals ──────────────────────────────────────────────────────
    total_rev  = sum(r["ytd"]["revenue"]    for r in valid)
    total_inc  = sum(r["ytd"]["net_income"] for r in valid)
    total_cash = sum(r["ytd"]["cash"]       for r in valid)
    avg_margin = round(sum(r["ytd"]["margin_pct"] for r in valid) / len(valid), 1) if valid else 0

    avg_rev = total_rev / months_elapsed if months_elapsed else 0
    avg_inc = total_inc / months_elapsed if months_elapsed else 0
    forecast_rev = round(total_rev + avg_rev * months_remaining)
    forecast_inc = round(total_inc + avg_inc * months_remaining)

    # ── Monthly portfolio rollup ───────────────────────────────────────────────
    ALL_MONTHS = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
    mp: dict[str, dict] = {}
    for r in valid:
        for m in r.get("monthly", []):
            mn = m["month"]
            if mn not in mp:
                mp[mn] = {"month": mn, "revenue": 0.0, "net_income": 0.0, "gross_profit": 0.0}
            mp[mn]["revenue"]      += m.get("revenue", 0)
            mp[mn]["net_income"]   += m.get("net_income", 0)
            mp[mn]["gross_profit"] += m.get("gross_profit", 0)

    monthly_actual = [mp[m] for m in ALL_MONTHS[:today.month] if m in mp]

    # Projected months (Jun → Dec) using avg monthly from actual data
    projected_monthly: list[dict] = []
    for i, mn in enumerate(ALL_MONTHS[today.month:], start=1):
        projected_monthly.append({
            "month":      mn,
            "revenue":    round(avg_rev),
            "net_income": round(avg_inc),
            "projected":  True,
        })

    # Accounting health summary
    total_months_open  = sum(r["accounting"]["months_open"]  for r in valid)
    total_uncat        = sum(r["accounting"]["total_uncat"]  for r in valid)
    max_days_behind    = max((r["accounting"]["days_behind"] for r in valid), default=0)
    avg_health         = round(sum(r["accounting"]["health_score"] for r in valid) / len(valid)) if valid else 0

    # IRS deadlines
    upcoming = get_upcoming_deadlines(within_days=90)
    overdue  = get_overdue_deadlines()

    return {
        "as_of":   today.isoformat(),
        "year":    yr,
        "months_elapsed": round(months_elapsed, 2),
        "portfolio": {
            "total_revenue_ytd":    total_rev,
            "total_net_income_ytd": total_inc,
            "total_cash":           total_cash,
            "avg_margin":           avg_margin,
            "companies_count":      len(valid),
            "forecast_revenue_eoy":    forecast_rev,
            "forecast_net_income_eoy": forecast_inc,
            "forecast_margin_eoy": round(forecast_inc / forecast_rev * 100, 1) if forecast_rev else 0,
        },
        "accounting_summary": {
            "total_months_open": total_months_open,
            "total_uncat":       total_uncat,
            "max_days_behind":   max_days_behind,
            "avg_health_score":  avg_health,
        },
        "companies":          results,
        "monthly_actual":     monthly_actual,
        "monthly_projected":  projected_monthly,
        "deadlines":          upcoming[:10],
        "overdue":            overdue[:5],
    }


# ── OAuth — start ──────────────────────────────────────────────────────────────
@app.get("/auth/connect/{index}")
async def auth_connect(index: int, request: Request):
    if not 1 <= index <= len(COMPANY_LIST):
        raise HTTPException(400, "Invalid company index")

    company = COMPANY_LIST[index - 1]
    state   = secrets.token_urlsafe(16)
    base_url = os.environ.get("APP_BASE_URL", str(request.base_url).rstrip("/"))
    redirect_uri = f"{base_url}/auth/callback"

    _oauth_states[state] = {"company": company, "redirect_uri": redirect_uri}

    params = {
        "client_id":     os.environ["QB_CLIENT_ID"],
        "response_type": "code",
        "scope":         SCOPES,
        "redirect_uri":  redirect_uri,
        "state":         state,
    }
    return RedirectResponse(f"{AUTH_URL}?{urllib.parse.urlencode(params)}")


# ── OAuth — callback ───────────────────────────────────────────────────────────
@app.get("/auth/callback")
async def auth_callback(code: str, state: str, realmId: str):
    import base64, requests as req_lib

    state_data = _oauth_states.pop(state, None)
    if not state_data:
        raise HTTPException(400, "Invalid or expired OAuth state.")

    company      = state_data["company"]
    redirect_uri = state_data["redirect_uri"]
    client_id    = os.environ["QB_CLIENT_ID"]
    client_secret = os.environ["QB_CLIENT_SECRET"]

    encoded = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    resp = req_lib.post(
        TOKEN_URL,
        headers={
            "Authorization": f"Basic {encoded}",
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        data={"grant_type": "authorization_code", "code": code, "redirect_uri": redirect_uri},
        timeout=30,
    )
    resp.raise_for_status()
    tokens = resp.json()

    upsert_company(
        name=company["name"],
        realm_id=realmId,
        env=company["env"],
        access_token=tokens["access_token"],
        refresh_token=tokens["refresh_token"],
    )

    return HTMLResponse(f"""
    <html><body style="font-family:sans-serif;padding:2em;text-align:center">
    <h2>&#10003; {company['name']} connected!</h2>
    <p>You can close this tab.</p>
    </body></html>
    """)
