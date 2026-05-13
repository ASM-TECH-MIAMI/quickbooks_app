"""
Supabase DB helpers — company token storage, conversation history, deadline tracking.
"""

import os
from typing import Optional
from supabase import create_client, Client

_client: Optional[Client] = None


def get_client() -> Client:
    global _client
    if _client is None:
        url = os.environ["SUPABASE_URL"]
        key = os.environ["SUPABASE_KEY"]
        _client = create_client(url, key)
    return _client


# ── Companies ──────────────────────────────────────────────────────────────────

def list_companies() -> list[dict]:
    r = get_client().table("companies").select("id,name,realm_id,env,updated_at").order("name").execute()
    return r.data


def get_company(name: str) -> Optional[dict]:
    r = get_client().table("companies").select("*").eq("name", name).maybe_single().execute()
    return r.data


def upsert_company(name: str, realm_id: str, env: str, access_token: str, refresh_token: str) -> dict:
    r = (
        get_client()
        .table("companies")
        .upsert(
            {
                "name": name,
                "realm_id": realm_id,
                "env": env,
                "access_token": access_token,
                "refresh_token": refresh_token,
            },
            on_conflict="name",
        )
        .execute()
    )
    return r.data[0]


def update_tokens(company_name: str, access_token: str, refresh_token: str):
    get_client().table("companies").update(
        {"access_token": access_token, "refresh_token": refresh_token}
    ).eq("name", company_name).execute()


# ── Conversations ──────────────────────────────────────────────────────────────

def create_conversation(company_id: int) -> str:
    r = (
        get_client()
        .table("conversations")
        .insert({"company_id": company_id, "messages": []})
        .execute()
    )
    return r.data[0]["id"]


def get_conversation(conversation_id: str) -> Optional[dict]:
    r = get_client().table("conversations").select("*").eq("id", conversation_id).maybe_single().execute()
    return r.data


def append_message(conversation_id: str, messages: list):
    get_client().table("conversations").update({"messages": messages}).eq("id", conversation_id).execute()


# ── Deadline status ────────────────────────────────────────────────────────────

def get_deadline_statuses(company_id: int) -> dict:
    r = get_client().table("deadline_status").select("deadline_id,status,notes").eq("company_id", company_id).execute()
    return {row["deadline_id"]: row for row in r.data}


def set_deadline_status(company_id: int, deadline_id: str, status: str, notes: str = ""):
    get_client().table("deadline_status").upsert(
        {"company_id": company_id, "deadline_id": deadline_id, "status": status, "notes": notes},
        on_conflict="company_id,deadline_id",
    ).execute()
