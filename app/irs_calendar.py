"""
IRS Tax Calendar — deadlines for LLCs (2025 & 2026)
Covers: Schedule C (sole prop), 1065 (partnership), 1120-S (S-Corp), 1120 (C-Corp).
Payroll: 941, 940, W-2/1099.
"""

from datetime import date, timedelta
from typing import Optional

# ── Deadline data ──────────────────────────────────────────────────────────────
# Each entry: {id, description, form, due_date, entity_types, notes}
# entity_types: list of "schedule_c", "partnership", "s_corp", "c_corp", "all", "payroll"

_DEADLINES_2025 = [
    # ── January ──
    {"id": "2025-W2-1099-furnish", "description": "Furnish W-2s to employees / 1099-NECs to contractors", "form": "W-2 / 1099-NEC", "due_date": date(2025, 1, 31), "entity_types": ["all"], "notes": "Must be postmarked or delivered to recipients."},
    {"id": "2025-1099-efile", "description": "E-file 1099-NECs with IRS", "form": "1099-NEC", "due_date": date(2025, 1, 31), "entity_types": ["all"], "notes": "Paper filing also due Jan 31 for 1099-NEC."},
    {"id": "2025-941-Q4-2024", "description": "File Q4 2024 payroll tax return", "form": "941", "due_date": date(2025, 1, 31), "entity_types": ["payroll"], "notes": "Or Feb 10 if all taxes deposited on time."},
    {"id": "2025-940-annual", "description": "File annual federal unemployment tax return", "form": "940", "due_date": date(2025, 1, 31), "entity_types": ["payroll"], "notes": "FUTA annual return."},

    # ── February ──
    {"id": "2025-W2-IRS-paper", "description": "Paper file W-2s with SSA", "form": "W-2", "due_date": date(2025, 2, 28), "entity_types": ["payroll"], "notes": "E-file deadline is March 31."},

    # ── March ──
    {"id": "2025-1065-original", "description": "Partnership return original due", "form": "1065", "due_date": date(2025, 3, 17), "entity_types": ["partnership"], "notes": "Mar 15 falls on Saturday → Mar 17."},
    {"id": "2025-1120S-original", "description": "S-Corp return original due", "form": "1120-S", "due_date": date(2025, 3, 17), "entity_types": ["s_corp"], "notes": "Mar 15 falls on Saturday → Mar 17."},
    {"id": "2025-1065-ext-request", "description": "Request 6-month extension for partnership", "form": "7004", "due_date": date(2025, 3, 17), "entity_types": ["partnership"], "notes": "Extension gives until Sep 15."},
    {"id": "2025-1120S-ext-request", "description": "Request 6-month extension for S-Corp", "form": "7004", "due_date": date(2025, 3, 17), "entity_types": ["s_corp"], "notes": "Extension gives until Sep 15."},
    {"id": "2025-W2-IRS-efile", "description": "E-file W-2s with SSA", "form": "W-2", "due_date": date(2025, 3, 31), "entity_types": ["payroll"], "notes": ""},
    {"id": "2025-1099-paper", "description": "Paper file 1099s with IRS (other than 1099-NEC)", "form": "1099-MISC etc.", "due_date": date(2025, 2, 28), "entity_types": ["all"], "notes": "1099-NEC paper was due Jan 31."},
    {"id": "2025-1099-efile-misc", "description": "E-file 1099-MISC and other 1099s with IRS", "form": "1099-MISC", "due_date": date(2025, 3, 31), "entity_types": ["all"], "notes": ""},

    # ── April ──
    {"id": "2025-1040-original", "description": "Individual return / Schedule C original due", "form": "1040 / Schedule C", "due_date": date(2025, 4, 15), "entity_types": ["schedule_c"], "notes": "Sole proprietors report business on Schedule C."},
    {"id": "2025-1120-original", "description": "C-Corp return original due (calendar year)", "form": "1120", "due_date": date(2025, 4, 15), "entity_types": ["c_corp"], "notes": ""},
    {"id": "2025-Q1-est-tax", "description": "Q1 2025 estimated tax payment", "form": "1040-ES / 1120-W", "due_date": date(2025, 4, 15), "entity_types": ["schedule_c", "partnership", "s_corp"], "notes": "Pass-through owners must pay estimated taxes."},
    {"id": "2025-941-Q1", "description": "File Q1 2025 payroll tax return", "form": "941", "due_date": date(2025, 4, 30), "entity_types": ["payroll"], "notes": "Or May 12 if all taxes deposited on time."},

    # ── June ──
    {"id": "2025-Q2-est-tax", "description": "Q2 2025 estimated tax payment", "form": "1040-ES / 1120-W", "due_date": date(2025, 6, 16), "entity_types": ["schedule_c", "partnership", "s_corp"], "notes": "Jun 15 falls on Sunday → Jun 16."},

    # ── July ──
    {"id": "2025-941-Q2", "description": "File Q2 2025 payroll tax return", "form": "941", "due_date": date(2025, 7, 31), "entity_types": ["payroll"], "notes": ""},

    # ── September ──
    {"id": "2025-Q3-est-tax", "description": "Q3 2025 estimated tax payment", "form": "1040-ES / 1120-W", "due_date": date(2025, 9, 15), "entity_types": ["schedule_c", "partnership", "s_corp"], "notes": ""},
    {"id": "2025-1065-ext-due", "description": "Partnership extended return due", "form": "1065", "due_date": date(2025, 9, 15), "entity_types": ["partnership"], "notes": "Final deadline — no further extensions."},
    {"id": "2025-1120S-ext-due", "description": "S-Corp extended return due", "form": "1120-S", "due_date": date(2025, 9, 15), "entity_types": ["s_corp"], "notes": "Final deadline — no further extensions."},

    # ── October ──
    {"id": "2025-941-Q3", "description": "File Q3 2025 payroll tax return", "form": "941", "due_date": date(2025, 10, 31), "entity_types": ["payroll"], "notes": ""},
    {"id": "2025-1040-ext-due", "description": "Individual / Schedule C extended return due", "form": "1040", "due_date": date(2025, 10, 15), "entity_types": ["schedule_c"], "notes": "Final deadline."},
    {"id": "2025-1120-ext-due", "description": "C-Corp extended return due (calendar year)", "form": "1120", "due_date": date(2025, 10, 15), "entity_types": ["c_corp"], "notes": "Final deadline."},

    # ── December ──
    {"id": "2025-Q4-est-tax", "description": "Q4 2025 estimated tax payment", "form": "1040-ES / 1120-W", "due_date": date(2026, 1, 15), "entity_types": ["schedule_c", "partnership", "s_corp"], "notes": "Due Jan 15 2026."},
]

_DEADLINES_2026 = [
    {"id": "2026-W2-1099-furnish", "description": "Furnish W-2s to employees / 1099-NECs to contractors", "form": "W-2 / 1099-NEC", "due_date": date(2026, 1, 31), "entity_types": ["all"], "notes": ""},
    {"id": "2026-1099-NEC-efile", "description": "E-file 1099-NECs with IRS", "form": "1099-NEC", "due_date": date(2026, 1, 31), "entity_types": ["all"], "notes": ""},
    {"id": "2026-941-Q4-2025", "description": "File Q4 2025 payroll tax return", "form": "941", "due_date": date(2026, 1, 31), "entity_types": ["payroll"], "notes": ""},
    {"id": "2026-940-annual", "description": "File annual federal unemployment tax return", "form": "940", "due_date": date(2026, 2, 2), "entity_types": ["payroll"], "notes": "Jan 31 falls on Saturday → Feb 2."},
    {"id": "2026-1065-original", "description": "Partnership return original due", "form": "1065", "due_date": date(2026, 3, 16), "entity_types": ["partnership"], "notes": "Mar 15 falls on Sunday → Mar 16."},
    {"id": "2026-1120S-original", "description": "S-Corp return original due", "form": "1120-S", "due_date": date(2026, 3, 16), "entity_types": ["s_corp"], "notes": ""},
    {"id": "2026-Q1-est-tax", "description": "Q1 2026 estimated tax payment", "form": "1040-ES", "due_date": date(2026, 4, 15), "entity_types": ["schedule_c", "partnership", "s_corp"], "notes": ""},
    {"id": "2026-1040-original", "description": "Individual return / Schedule C original due", "form": "1040", "due_date": date(2026, 4, 15), "entity_types": ["schedule_c"], "notes": ""},
    {"id": "2026-1120-original", "description": "C-Corp return original due", "form": "1120", "due_date": date(2026, 4, 15), "entity_types": ["c_corp"], "notes": ""},
    {"id": "2026-941-Q1", "description": "File Q1 2026 payroll tax return", "form": "941", "due_date": date(2026, 4, 30), "entity_types": ["payroll"], "notes": ""},
    {"id": "2026-Q2-est-tax", "description": "Q2 2026 estimated tax payment", "form": "1040-ES", "due_date": date(2026, 6, 15), "entity_types": ["schedule_c", "partnership", "s_corp"], "notes": ""},
    {"id": "2026-941-Q2", "description": "File Q2 2026 payroll tax return", "form": "941", "due_date": date(2026, 7, 31), "entity_types": ["payroll"], "notes": ""},
    {"id": "2026-Q3-est-tax", "description": "Q3 2026 estimated tax payment", "form": "1040-ES", "due_date": date(2026, 9, 15), "entity_types": ["schedule_c", "partnership", "s_corp"], "notes": ""},
    {"id": "2026-1065-ext-due", "description": "Partnership extended return due", "form": "1065", "due_date": date(2026, 9, 15), "entity_types": ["partnership"], "notes": ""},
    {"id": "2026-1120S-ext-due", "description": "S-Corp extended return due", "form": "1120-S", "due_date": date(2026, 9, 15), "entity_types": ["s_corp"], "notes": ""},
    {"id": "2026-941-Q3", "description": "File Q3 2026 payroll tax return", "form": "941", "due_date": date(2026, 10, 31), "entity_types": ["payroll"], "notes": ""},
    {"id": "2026-1040-ext-due", "description": "Individual / Schedule C extended return due", "form": "1040", "due_date": date(2026, 10, 15), "entity_types": ["schedule_c"], "notes": ""},
    {"id": "2026-1120-ext-due", "description": "C-Corp extended return due", "form": "1120", "due_date": date(2026, 10, 15), "entity_types": ["c_corp"], "notes": ""},
    {"id": "2026-Q4-est-tax", "description": "Q4 2026 estimated tax payment", "form": "1040-ES", "due_date": date(2027, 1, 15), "entity_types": ["schedule_c", "partnership", "s_corp"], "notes": ""},
]

ALL_DEADLINES = _DEADLINES_2025 + _DEADLINES_2026


def _serialize(d: dict) -> dict:
    return {**d, "due_date": d["due_date"].isoformat()}


# ── Public API ─────────────────────────────────────────────────────────────────

def get_upcoming_deadlines(
    entity_type: Optional[str] = None,
    within_days: int = 90,
    include_payroll: bool = True,
    today: Optional[date] = None,
) -> list[dict]:
    """
    Return deadlines due within `within_days` from today.

    entity_type: "schedule_c" | "partnership" | "s_corp" | "c_corp" | None (all)
    include_payroll: whether to include 941/940/W-2 deadlines
    """
    today = today or date.today()
    cutoff = today + timedelta(days=within_days)
    results = []
    for d in ALL_DEADLINES:
        if d["due_date"] < today:
            continue
        if d["due_date"] > cutoff:
            continue
        types = d["entity_types"]
        if not include_payroll and "payroll" in types and types == ["payroll"]:
            continue
        if entity_type and entity_type not in types and "all" not in types and "payroll" not in types:
            if entity_type != "payroll":
                continue
        results.append(_serialize(d))
    results.sort(key=lambda x: x["due_date"])
    return results


def get_all_deadlines(
    entity_type: Optional[str] = None,
    year: Optional[int] = None,
) -> list[dict]:
    """Return all deadlines, optionally filtered by entity type and/or year."""
    results = []
    for d in ALL_DEADLINES:
        if year and d["due_date"].year != year:
            continue
        if entity_type:
            types = d["entity_types"]
            if entity_type not in types and "all" not in types:
                continue
        results.append(_serialize(d))
    results.sort(key=lambda x: x["due_date"])
    return results


def get_overdue_deadlines(
    entity_type: Optional[str] = None,
    today: Optional[date] = None,
) -> list[dict]:
    """Return deadlines that have already passed."""
    today = today or date.today()
    results = []
    for d in ALL_DEADLINES:
        if d["due_date"] >= today:
            continue
        if entity_type:
            types = d["entity_types"]
            if entity_type not in types and "all" not in types:
                continue
        results.append(_serialize(d))
    results.sort(key=lambda x: x["due_date"], reverse=True)
    return results
