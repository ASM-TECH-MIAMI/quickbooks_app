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

        def _val(rows, label):
            for r in rows:
                if r.get("type") == "Section":
                    for sub in r.get("Rows", {}).get("Row", []):
                        if sub.get("type") == "Total" and label.lower() in sub.get("Header", {}).get("ColData", [{}])[0].get("value", "").lower():
                            cols = sub.get("ColData", [])
                            return float(cols[1]["value"]) if len(cols) > 1 else 0
            return 0

        rows = pl.get("Rows", {}).get("Row", [])

        # Recursively collect all Summary rows into a flat dict: label → value
        def collect_summaries(rows_list: list) -> dict:
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
                    # Recurse into sub-rows
                    sub = r.get("Rows", {}).get("Row", [])
                    if sub:
                        result.update(collect_summaries(sub))
            return result

        summaries = collect_summaries(rows)

        revenue     = next((v for k, v in summaries.items() if "total income" in k or ("total" in k and "revenue" in k)), 0)
        gross_profit = summaries.get("gross profit", 0)
        net_income  = next((v for k, v in summaries.items() if "net income" in k or "net profit" in k), 0)

        # Cash from cash flow end balance
        cash = 0
        cf_rows = cf.get("Rows", {}).get("Row", [])
        for cr in cf_rows:
            if cr.get("type") == "Section":
                summ = cr.get("Summary", {}).get("ColData", [])
                lbl  = summ[0].get("value", "").lower() if summ else ""
                if "ending" in lbl or "end" in lbl:
                    cash = float(summ[1]["value"]) if len(summ) > 1 else 0

        margin = round((net_income / revenue * 100), 1) if revenue else 0

        return {
            "name":        name,
            "revenue":     revenue,
            "gross_profit": gross_profit,
            "net_income":  net_income,
            "margin_pct":  margin,
            "cash":        cash,
            "period":      f"YTD {today.year}",
            "error":       None,
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
