"""
QuickBooks Multi-Company OAuth2 Setup
======================================
Run once per company to capture and store refresh tokens.

Prerequisites (one-time):
  1. In developer.intuit.com → Your App → Keys & Credentials → Redirect URIs
     add:  http://localhost:8080/callback
  2. pip install -r requirements.txt

Usage:
  python setup_auth.py            # shows menu, connect all or pick
  python setup_auth.py --list     # show connection status only
"""

import argparse
import base64
import json
import os
import secrets
import sys
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import requests
from dotenv import load_dotenv

# ── Config ────────────────────────────────────────────────────────────────────
load_dotenv()

CREDENTIALS_FILE = Path(__file__).parent / "credentials.json"
REDIRECT_URI     = "http://localhost:8765/callback"
AUTH_URL         = "https://appcenter.intuit.com/connect/oauth2"
TOKEN_URL        = "https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer"
SCOPES           = "com.intuit.quickbooks.accounting"

COMPANIES = [
    {"name": "Miami Image Society LLC",  "env": "production"},
    {"name": "Lush Media Group LLC",      "env": "production"},
    {"name": "ASM Tech Media Group LLC",  "env": "production"},
    {"name": "Atomick LLC",               "env": "production"},
    {"name": "Developer Sandbox",         "env": "sandbox"},
]

# ── Credential store ──────────────────────────────────────────────────────────
def load_credentials() -> dict:
    if CREDENTIALS_FILE.exists():
        return json.loads(CREDENTIALS_FILE.read_text())
    # Bootstrap from .env
    cid = os.environ.get("QB_CLIENT_ID", "")
    sec = os.environ.get("QB_CLIENT_SECRET", "")
    if not cid or not sec:
        print("ERROR: QB_CLIENT_ID / QB_CLIENT_SECRET not found.")
        print("  Either set them in .env or run with credentials.json present.")
        sys.exit(1)
    return {"client_id": cid, "client_secret": sec, "companies": {}}

def save_credentials(creds: dict):
    CREDENTIALS_FILE.write_text(json.dumps(creds, indent=2))
    CREDENTIALS_FILE.chmod(0o600)
    print(f"  ✓  Saved to {CREDENTIALS_FILE.name}")

# ── One-shot OAuth callback server ────────────────────────────────────────────
_callback_result: dict = {}

class _Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/callback":
            params = urllib.parse.parse_qs(parsed.query)
            _callback_result.update({
                "code":    params.get("code",    [None])[0],
                "realmId": params.get("realmId", [None])[0],
                "error":   params.get("error",   [None])[0],
            })
            body = (
                b"<html><body style='font-family:sans-serif;padding:2em'>"
                b"<h2>&#10003; Authorization complete</h2>"
                b"<p>You may close this tab and return to the terminal.</p>"
                b"</body></html>"
            )
        else:
            body = b"<h1>404</h1>"
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(body)
        self.server._done = True

    def log_message(self, *_):
        pass  # silence access logs

def _wait_for_callback(port: int = 8765) -> dict:
    _callback_result.clear()
    server = HTTPServer(("localhost", port), _Handler)
    server._done = False
    while not server._done:
        server.handle_request()
    server.server_close()
    return dict(_callback_result)

# ── Token exchange ────────────────────────────────────────────────────────────
def exchange_code(client_id: str, client_secret: str, code: str) -> dict:
    encoded = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    resp = requests.post(
        TOKEN_URL,
        headers={
            "Authorization": f"Basic {encoded}",
            "Accept":        "application/json",
            "Content-Type":  "application/x-www-form-urlencoded",
        },
        data={
            "grant_type":   "authorization_code",
            "code":         code,
            "redirect_uri": REDIRECT_URI,
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()

# ── Per-company connect flow ──────────────────────────────────────────────────
def connect_company(creds: dict, company: dict) -> bool:
    name       = company["name"]
    is_sandbox = company["env"] == "sandbox"

    print(f"\n{'─' * 62}")
    print(f"  Connecting: {name}  ({'sandbox' if is_sandbox else 'production'})")
    print(f"{'─' * 62}")

    state  = secrets.token_urlsafe(16)
    params = {
        "client_id":     creds["client_id"],
        "response_type": "code",
        "scope":         SCOPES,
        "redirect_uri":  REDIRECT_URI,
        "state":         state,
    }
    auth_link = f"{AUTH_URL}?{urllib.parse.urlencode(params)}"

    print("\n  Opening your browser for QuickBooks authorization…")
    print(f"  (If it doesn't open automatically, visit the URL below)\n")
    print(f"  {auth_link}\n")
    webbrowser.open(auth_link)

    print("  Waiting for authorization…  (listening on localhost:8080)")
    result = _wait_for_callback()

    if result.get("error"):
        print(f"  ✗  Authorization failed: {result['error']}")
        return False

    code     = result["code"]
    realm_id = result["realmId"]
    print(f"  ✓  Got authorization code  (realm_id = {realm_id})")

    print("  Exchanging code for tokens…")
    try:
        tokens = exchange_code(creds["client_id"], creds["client_secret"], code)
    except requests.HTTPError as exc:
        print(f"  ✗  Token exchange failed: {exc}")
        return False

    creds.setdefault("companies", {})[name] = {
        "realm_id":      realm_id,
        "env":           company["env"],
        "access_token":  tokens.get("access_token"),
        "refresh_token": tokens.get("refresh_token"),
        "token_type":    tokens.get("token_type", "Bearer"),
    }
    print(f"  ✓  Tokens stored for {name}")
    return True

# ── CLI ───────────────────────────────────────────────────────────────────────
def print_status(creds: dict):
    connected = creds.get("companies", {})
    print("\n  QuickBooks company connection status:")
    print(f"  {'#':<3} {'Status':<10} {'Company':<35} {'Env'}")
    print(f"  {'─'*3} {'─'*10} {'─'*35} {'─'*12}")
    for i, c in enumerate(COMPANIES, 1):
        status = "✓ connected" if c["name"] in connected else "  pending"
        print(f"  {i:<3} {status:<10} {c['name']:<35} {c['env']}")
    print()

def main():
    parser = argparse.ArgumentParser(description="QB multi-company OAuth setup")
    parser.add_argument("--list", action="store_true", help="Show connection status and exit")
    args = parser.parse_args()

    print("\n╔══════════════════════════════════════════════════════════╗")
    print("║   QuickBooks Multi-Company Auth Setup                    ║")
    print("╚══════════════════════════════════════════════════════════╝")

    creds = load_credentials()
    print_status(creds)

    if args.list:
        return

    print("  Connect which companies?")
    print("  Press Enter to connect ALL, or enter numbers (e.g. 1,3,5): ", end="")
    choice = input().strip()

    if choice == "":
        to_connect = COMPANIES
    else:
        try:
            indices    = [int(x.strip()) - 1 for x in choice.split(",")]
            to_connect = [COMPANIES[i] for i in indices]
        except (ValueError, IndexError):
            print("  Invalid selection.")
            sys.exit(1)

    success = 0
    for company in to_connect:
        if connect_company(creds, company):
            save_credentials(creds)
            success += 1

    print(f"\n{'═' * 62}")
    print(f"  Done — {success}/{len(to_connect)} companies connected.")
    print(f"  Tokens stored in: credentials.json  (chmod 600)")
    print(f"{'═' * 62}\n")

if __name__ == "__main__":
    main()
