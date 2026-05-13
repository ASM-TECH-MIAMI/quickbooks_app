"""
QuickBooks Online — multi-company API client
=============================================
Handles token refresh automatically.  Each instance is bound to one company.

Usage:
    from qbo_client import QBOClient, list_companies

    # See all connected companies
    list_companies()

    # Connect to a specific company
    client = QBOClient("Miami Image Society LLC")

    # Reports
    pl   = client.profit_and_loss("2025-01-01", "2025-12-31")
    bs   = client.balance_sheet("2025-01-01", "2025-12-31")
    cf   = client.cash_flow("2025-01-01", "2025-12-31")
    ar   = client.ar_aging()
    ap   = client.ap_aging()
    info = client.company_info()

    # SQL-style queries (returns list of QB entity dicts)
    invoices = client.query("SELECT * FROM Invoice WHERE DueDate < '2025-12-31'")
    vendors  = client.query("SELECT * FROM Vendor MAXRESULTS 100")

    # Raw REST access
    data = client.get("reports/ProfitAndLoss", {"start_date": "2025-01-01", "end_date": "2025-12-31"})
"""

import base64
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

import requests

# ── Constants ─────────────────────────────────────────────────────────────────
TOKEN_URL     = "https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer"
PROD_BASE     = "https://quickbooks.api.intuit.com/v3/company"
SAND_BASE     = "https://sandbox-quickbooks.api.intuit.com/v3/company"
MINOR_VERSION = 65


# ── Client ────────────────────────────────────────────────────────────────────
class QBOClient:
    """Authenticated QBO REST client bound to a single company."""

    def __init__(self, company_name: str, realm_id: str, env: str,
                 access_token: str, refresh_token: str):
        self.company_name  = company_name
        self._realm_id     = realm_id
        self._refresh_tok  = refresh_token
        base               = SAND_BASE if env == "sandbox" else PROD_BASE
        self.base_url      = f"{base}/{realm_id}"
        self._access_token: Optional[str]      = access_token
        self._token_expiry: Optional[datetime] = None  # refresh on first call

    @classmethod
    def from_db(cls, company_row: dict) -> "QBOClient":
        """Construct from a Supabase companies row."""
        return cls(
            company_name=company_row["name"],
            realm_id=company_row["realm_id"],
            env=company_row["env"],
            access_token=company_row.get("access_token", ""),
            refresh_token=company_row["refresh_token"],
        )

    # ── Token management ──────────────────────────────────────────────────────
    def _refresh_access_token(self):
        client_id     = os.environ["QB_CLIENT_ID"]
        client_secret = os.environ["QB_CLIENT_SECRET"]
        encoded       = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()

        resp = requests.post(
            TOKEN_URL,
            headers={
                "Authorization": f"Basic {encoded}",
                "Accept":        "application/json",
                "Content-Type":  "application/x-www-form-urlencoded",
            },
            data={
                "grant_type":    "refresh_token",
                "refresh_token": self._refresh_tok,
            },
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()

        self._access_token = data["access_token"]
        self._token_expiry = datetime.utcnow() + timedelta(
            seconds=data.get("expires_in", 3600) - 60
        )
        if "refresh_token" in data:
            self._refresh_tok = data["refresh_token"]

        # Persist refreshed tokens to DB
        try:
            from .db import update_tokens
            update_tokens(self.company_name, self._access_token, self._refresh_tok)
        except Exception:
            pass

    def _ensure_valid_token(self):
        if self._token_expiry is None or datetime.utcnow() >= self._token_expiry:
            self._refresh_access_token()

    # ── Base HTTP methods ─────────────────────────────────────────────────────
    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self._access_token}",
            "Accept":        "application/json",
            "Content-Type":  "application/json",
        }

    def get(self, endpoint: str, params: Optional[dict] = None) -> dict:
        """GET {base_url}/{endpoint} with optional query params."""
        self._ensure_valid_token()
        url  = f"{self.base_url}/{endpoint}"
        resp = requests.get(url, headers=self._headers(), params=params, timeout=30)
        resp.raise_for_status()
        return resp.json()

    def post(self, endpoint: str, payload: dict) -> dict:
        """POST {base_url}/{endpoint} with JSON body."""
        self._ensure_valid_token()
        url  = f"{self.base_url}/{endpoint}"
        resp = requests.post(url, headers=self._headers(), json=payload, timeout=30)
        resp.raise_for_status()
        return resp.json()

    def query(self, sql: str) -> Any:
        """
        Execute a QBO SQL-style query.
        Returns the raw QueryResponse dict (varies by entity type).

        Examples:
            client.query("SELECT * FROM Invoice WHERE DueDate < '2026-01-01'")
            client.query("SELECT * FROM Vendor MAXRESULTS 100")
            client.query("SELECT * FROM Account WHERE AccountType = 'Expense'")
        """
        self._ensure_valid_token()
        resp = requests.get(
            f"{self.base_url}/query",
            headers=self._headers(),
            params={"query": sql, "minorversion": MINOR_VERSION},
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json().get("QueryResponse", {})

    # ── Report helpers ────────────────────────────────────────────────────────
    def company_info(self) -> dict:
        """Basic company info (name, address, industry, fiscal year…)."""
        return self.get(f"companyinfo/{self._realm_id}")

    def profit_and_loss(
        self,
        start_date: str,
        end_date: str,
        accounting_method: str = "Accrual",
    ) -> dict:
        """P&L report.  Dates in YYYY-MM-DD format."""
        return self.get(
            "reports/ProfitAndLoss",
            {
                "start_date":         start_date,
                "end_date":           end_date,
                "accounting_method":  accounting_method,
                "minorversion":       MINOR_VERSION,
            },
        )

    def balance_sheet(
        self,
        start_date: str,
        end_date: str,
        accounting_method: str = "Accrual",
    ) -> dict:
        return self.get(
            "reports/BalanceSheet",
            {
                "start_date":        start_date,
                "end_date":          end_date,
                "accounting_method": accounting_method,
                "minorversion":      MINOR_VERSION,
            },
        )

    def cash_flow(self, start_date: str, end_date: str) -> dict:
        return self.get(
            "reports/CashFlow",
            {
                "start_date":   start_date,
                "end_date":     end_date,
                "minorversion": MINOR_VERSION,
            },
        )

    def ar_aging(self, aging_period: int = 30, num_periods: int = 4) -> dict:
        """Accounts Receivable aging summary."""
        return self.get(
            "reports/AgedReceivables",
            {"num_periods": num_periods, "aging_period": aging_period},
        )

    def ap_aging(self, aging_period: int = 30, num_periods: int = 4) -> dict:
        """Accounts Payable aging summary."""
        return self.get(
            "reports/AgedPayables",
            {"num_periods": num_periods, "aging_period": aging_period},
        )

    def trial_balance(self, start_date: str, end_date: str) -> dict:
        return self.get(
            "reports/TrialBalance",
            {"start_date": start_date, "end_date": end_date, "minorversion": MINOR_VERSION},
        )

    # ── Entity queries (convenience wrappers) ─────────────────────────────────
    def invoices(self, limit: int = 100) -> list:
        r = self.query(f"SELECT * FROM Invoice MAXRESULTS {limit}")
        return r.get("Invoice", [])

    def customers(self, limit: int = 100) -> list:
        r = self.query(f"SELECT * FROM Customer MAXRESULTS {limit}")
        return r.get("Customer", [])

    def vendors(self, limit: int = 100) -> list:
        r = self.query(f"SELECT * FROM Vendor MAXRESULTS {limit}")
        return r.get("Vendor", [])

    def expenses(self, start_date: str, end_date: str, limit: int = 200) -> list:
        r = self.query(
            f"SELECT * FROM Purchase WHERE TxnDate >= '{start_date}' "
            f"AND TxnDate <= '{end_date}' MAXRESULTS {limit}"
        )
        return r.get("Purchase", [])

    def accounts(self) -> list:
        r = self.query("SELECT * FROM Account MAXRESULTS 200")
        return r.get("Account", [])

    # ── Dunder ────────────────────────────────────────────────────────────────
    def __repr__(self) -> str:
        env = self._company.get("env", "?")
        return f"QBOClient(company='{self.company_name}', env={env}, realm={self._realm_id})"
