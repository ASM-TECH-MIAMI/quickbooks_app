"""
QB AI Agent — tool definitions, dispatcher, and CLI entry point.
"""

import json
import os
import sys
from datetime import date
from pathlib import Path
from typing import Any

import anthropic
from dotenv import dotenv_values

# Load .env overriding ambient env vars (for CLI use)
_env_path = Path(__file__).parent.parent / ".env"
if _env_path.exists():
    for _k, _v in dotenv_values(_env_path).items():
        if _v:
            os.environ[_k] = _v

from .qbo_client import QBOClient
from .irs_calendar import get_upcoming_deadlines, get_all_deadlines, get_overdue_deadlines

# ── Tool definitions ───────────────────────────────────────────────────────────

TOOLS: list[dict] = [
    {
        "name": "get_company_info",
        "description": "Get basic company information: name, address, industry, fiscal year start, EIN (if available).",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "get_profit_and_loss",
        "description": (
            "Get the Profit & Loss (Income Statement) for a date range. "
            "Returns revenue, COGS, gross profit, operating expenses, and net income."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "start_date": {"type": "string", "description": "Start date in YYYY-MM-DD format"},
                "end_date":   {"type": "string", "description": "End date in YYYY-MM-DD format"},
                "accounting_method": {
                    "type": "string",
                    "enum": ["Accrual", "Cash"],
                    "description": "Accounting method (default: Accrual)",
                },
            },
            "required": ["start_date", "end_date"],
        },
    },
    {
        "name": "get_balance_sheet",
        "description": "Get the Balance Sheet: assets, liabilities, and equity at a point in time.",
        "input_schema": {
            "type": "object",
            "properties": {
                "start_date": {"type": "string", "description": "Start date in YYYY-MM-DD"},
                "end_date":   {"type": "string", "description": "End date in YYYY-MM-DD"},
            },
            "required": ["start_date", "end_date"],
        },
    },
    {
        "name": "get_cash_flow",
        "description": "Get the Cash Flow statement for a date range.",
        "input_schema": {
            "type": "object",
            "properties": {
                "start_date": {"type": "string"},
                "end_date":   {"type": "string"},
            },
            "required": ["start_date", "end_date"],
        },
    },
    {
        "name": "get_ar_aging",
        "description": "Get Accounts Receivable aging — which customers owe money and how long overdue.",
        "input_schema": {
            "type": "object",
            "properties": {
                "aging_period": {"type": "integer", "description": "Days per aging bucket (default: 30)"},
                "num_periods":  {"type": "integer", "description": "Number of buckets (default: 4)"},
            },
            "required": [],
        },
    },
    {
        "name": "get_ap_aging",
        "description": "Get Accounts Payable aging — which vendors are owed money and how long overdue.",
        "input_schema": {
            "type": "object",
            "properties": {
                "aging_period": {"type": "integer", "description": "Days per aging bucket (default: 30)"},
                "num_periods":  {"type": "integer", "description": "Number of buckets (default: 4)"},
            },
            "required": [],
        },
    },
    {
        "name": "get_trial_balance",
        "description": "Get the Trial Balance — all accounts with their debit/credit balances.",
        "input_schema": {
            "type": "object",
            "properties": {
                "start_date": {"type": "string"},
                "end_date":   {"type": "string"},
            },
            "required": ["start_date", "end_date"],
        },
    },
    {
        "name": "query_invoices",
        "description": "List recent invoices with status, amounts, and customer names.",
        "input_schema": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "Max number of invoices to return (default: 50)"},
            },
            "required": [],
        },
    },
    {
        "name": "query_customers",
        "description": "List customers in the company.",
        "input_schema": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "Max number of customers (default: 100)"},
            },
            "required": [],
        },
    },
    {
        "name": "query_vendors",
        "description": "List vendors (suppliers) in the company.",
        "input_schema": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "Max number of vendors (default: 100)"},
            },
            "required": [],
        },
    },
    {
        "name": "query_expenses",
        "description": "List expenses/purchases for a date range.",
        "input_schema": {
            "type": "object",
            "properties": {
                "start_date": {"type": "string"},
                "end_date":   {"type": "string"},
                "limit":      {"type": "integer", "description": "Max records (default: 200)"},
            },
            "required": ["start_date", "end_date"],
        },
    },
    {
        "name": "query_accounts",
        "description": "List all chart of accounts — account names, types, and balances.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "run_qbo_query",
        "description": (
            "Run a raw SQL-style QBO query for custom lookups. "
            "E.g. \"SELECT * FROM Bill WHERE TxnDate >= '2025-01-01'\". "
            "Supported entities: Invoice, Bill, Payment, Customer, Vendor, Account, "
            "Purchase, Deposit, JournalEntry, Employee, Item."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "sql": {"type": "string", "description": "The QBO SQL query string"},
            },
            "required": ["sql"],
        },
    },
    {
        "name": "get_irs_upcoming_deadlines",
        "description": (
            "Get upcoming IRS tax deadlines. "
            "Optionally filter by entity type and time window."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "entity_type": {
                    "type": "string",
                    "enum": ["schedule_c", "partnership", "s_corp", "c_corp"],
                    "description": "Filter by tax entity type. Omit to return all.",
                },
                "within_days": {
                    "type": "integer",
                    "description": "Return deadlines due within this many days (default: 90)",
                },
                "include_payroll": {
                    "type": "boolean",
                    "description": "Include payroll deadlines (941, 940, W-2). Default: true",
                },
            },
            "required": [],
        },
    },
    {
        "name": "get_irs_all_deadlines",
        "description": "Get all IRS deadlines for a year, optionally filtered by entity type.",
        "input_schema": {
            "type": "object",
            "properties": {
                "year": {
                    "type": "integer",
                    "description": "Tax year (2025 or 2026). Omit for both years.",
                },
                "entity_type": {
                    "type": "string",
                    "enum": ["schedule_c", "partnership", "s_corp", "c_corp", "payroll"],
                },
            },
            "required": [],
        },
    },
    {
        "name": "get_irs_overdue_deadlines",
        "description": "Get IRS deadlines that have already passed (for catching missed filings).",
        "input_schema": {
            "type": "object",
            "properties": {
                "entity_type": {
                    "type": "string",
                    "enum": ["schedule_c", "partnership", "s_corp", "c_corp", "payroll"],
                },
            },
            "required": [],
        },
    },
]


# ── Tool dispatcher ────────────────────────────────────────────────────────────

def dispatch_tool_sync(name: str, inputs: dict, client: QBOClient) -> Any:
    return dispatch_tool(name, inputs, client)


def dispatch_tool(name: str, inputs: dict, client: QBOClient) -> Any:
    if name == "get_company_info":
        return client.company_info()

    elif name == "get_profit_and_loss":
        return client.profit_and_loss(
            inputs["start_date"],
            inputs["end_date"],
            inputs.get("accounting_method", "Accrual"),
        )

    elif name == "get_balance_sheet":
        return client.balance_sheet(inputs["start_date"], inputs["end_date"])

    elif name == "get_cash_flow":
        return client.cash_flow(inputs["start_date"], inputs["end_date"])

    elif name == "get_ar_aging":
        return client.ar_aging(
            inputs.get("aging_period", 30),
            inputs.get("num_periods", 4),
        )

    elif name == "get_ap_aging":
        return client.ap_aging(
            inputs.get("aging_period", 30),
            inputs.get("num_periods", 4),
        )

    elif name == "get_trial_balance":
        return client.trial_balance(inputs["start_date"], inputs["end_date"])

    elif name == "query_invoices":
        return client.invoices(inputs.get("limit", 50))

    elif name == "query_customers":
        return client.customers(inputs.get("limit", 100))

    elif name == "query_vendors":
        return client.vendors(inputs.get("limit", 100))

    elif name == "query_expenses":
        return client.expenses(
            inputs["start_date"],
            inputs["end_date"],
            inputs.get("limit", 200),
        )

    elif name == "query_accounts":
        return client.accounts()

    elif name == "run_qbo_query":
        return client.query(inputs["sql"])

    elif name == "get_irs_upcoming_deadlines":
        return get_upcoming_deadlines(
            entity_type=inputs.get("entity_type"),
            within_days=inputs.get("within_days", 90),
            include_payroll=inputs.get("include_payroll", True),
        )

    elif name == "get_irs_all_deadlines":
        return get_all_deadlines(
            entity_type=inputs.get("entity_type"),
            year=inputs.get("year"),
        )

    elif name == "get_irs_overdue_deadlines":
        return get_overdue_deadlines(entity_type=inputs.get("entity_type"))

    else:
        return {"error": f"Unknown tool: {name}"}


# ── Agent loop ─────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are a smart financial assistant for a US small business owner with multiple LLCs.
You have direct access to live QuickBooks Online data and an IRS tax calendar.

Your three main jobs:
1. **Business Q&A** — Answer questions about revenue, expenses, cash flow, customers, vendors, etc.
   Pull real data from QuickBooks to give precise, data-backed answers.
2. **Accountant audit** — Spot anomalies: uncategorized transactions, duplicate entries,
   missing invoices, accounts with unexpected balances, reconciliation gaps.
3. **Tax & accounting deadlines** — Tell the owner what IRS filings are coming up,
   what's overdue, and what they need to prepare. Tailor to the entity type when known.

Guidelines:
- Always prefer fetching real data over guessing. Use tools freely.
- When presenting financial figures, format numbers with commas and $ signs.
- Be concise but complete. Bullet points for lists; tables (markdown) for comparisons.
- If you're unsure about the entity type (Schedule C, partnership, S-Corp, C-Corp),
  ask the user — it affects which tax deadlines apply.
- Today's date is {today}.
- The currently selected company is: {company}.
- Respond in the same language the user uses (Spanish or English).
"""


def run_agent(company_name: str):
    from .db import get_company
    row = get_company(company_name)
    if not row:
        print(f"Company '{company_name}' not in DB. Run OAuth connect first.")
        return
    qbo = QBOClient.from_db(row)
    ai  = anthropic.Anthropic()

    system = SYSTEM_PROMPT.format(
        today=date.today().isoformat(),
        company=company_name,
    )

    messages: list[dict] = []

    print(f"\n{'='*60}")
    print(f"  QB AI Agent — {company_name}")
    print(f"  Today: {date.today().isoformat()}")
    print(f"  Type 'exit' or 'quit' to end.")
    print(f"{'='*60}\n")

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nSaliendo.")
            break

        if not user_input:
            continue
        if user_input.lower() in {"exit", "quit", "salir", "q"}:
            print("Hasta luego.")
            break

        messages.append({"role": "user", "content": user_input})

        # Agentic loop: keep going until Claude stops using tools
        while True:
            response = ai.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=4096,
                system=system,
                tools=TOOLS,
                messages=messages,
            )

            # Collect all content blocks
            assistant_content = response.content
            messages.append({"role": "assistant", "content": assistant_content})

            if response.stop_reason == "end_turn":
                # Print text response
                for block in assistant_content:
                    if hasattr(block, "text"):
                        print(f"\nAgent: {block.text}\n")
                break

            elif response.stop_reason == "tool_use":
                tool_results = []
                for block in assistant_content:
                    if block.type == "tool_use":
                        tool_name   = block.name
                        tool_inputs = block.input
                        print(f"  [tool: {tool_name}]", end="", flush=True)
                        try:
                            result = dispatch_tool(tool_name, tool_inputs, qbo)
                            result_str = json.dumps(result, default=str)
                            print(" ✓")
                        except Exception as exc:
                            result_str = json.dumps({"error": str(exc)})
                            print(f" ✗ {exc}")

                        tool_results.append({
                            "type":        "tool_result",
                            "tool_use_id": block.id,
                            "content":     result_str,
                        })

                messages.append({"role": "user", "content": tool_results})

            else:
                # Unexpected stop reason
                print(f"[stop_reason={response.stop_reason}]")
                break


# ── Entry point ────────────────────────────────────────────────────────────────

def main():
    from .db import list_companies as db_list
    companies = [c["name"] for c in db_list()]

    if not companies:
        print("No companies connected yet. Open the web UI and connect a company first.")
        sys.exit(1)

    if len(sys.argv) > 1:
        company_name = " ".join(sys.argv[1:])
    else:
        print("\nSelecciona una empresa:")
        for i, name in enumerate(companies, 1):
            print(f"  {i}. {name}")
        while True:
            choice = input("\nNúmero o nombre: ").strip()
            if choice.isdigit():
                idx = int(choice) - 1
                if 0 <= idx < len(companies):
                    company_name = companies[idx]
                    break
                print("Número fuera de rango.")
            elif choice in companies:
                company_name = choice
                break
            else:
                print("No encontrado. Intenta de nuevo.")

    run_agent(company_name)


if __name__ == "__main__":
    main()


if __name__ == "__main__":
    main()
