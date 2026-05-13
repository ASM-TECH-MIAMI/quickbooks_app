"""
connect_one.py <company_index>
Connects a single company (1-5) without any interactive prompts.
Prints the auth URL to stdout, then waits for the callback.
"""
import base64
import json
import secrets
import sys
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import requests
from dotenv import load_dotenv

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

_result: dict = {}

class _Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/callback":
            params = urllib.parse.parse_qs(parsed.query)
            _result.update({
                "code":    params.get("code",    [None])[0],
                "realmId": params.get("realmId", [None])[0],
                "error":   params.get("error",   [None])[0],
            })
            body = b"<html><body style='font-family:sans-serif;padding:2em'><h2>&#10003; Authorization complete &mdash; you may close this tab.</h2></body></html>"
        else:
            body = b"<h1>404</h1>"
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(body)
        self.server._done = True
    def log_message(self, *_): pass

def main():
    if len(sys.argv) < 2:
        print("Usage: python connect_one.py <1-5>"); sys.exit(1)

    idx     = int(sys.argv[1]) - 1
    company = COMPANIES[idx]
    name    = company["name"]

    creds = json.loads(CREDENTIALS_FILE.read_text())

    state  = secrets.token_urlsafe(16)
    params = {
        "client_id":     creds["client_id"],
        "response_type": "code",
        "scope":         SCOPES,
        "redirect_uri":  REDIRECT_URI,
        "state":         state,
    }
    auth_link = f"{AUTH_URL}?{urllib.parse.urlencode(params)}"

    print(f"COMPANY: {name}")
    print(f"AUTH_URL: {auth_link}")
    print("WAITING_FOR_CALLBACK", flush=True)

    server = HTTPServer(("localhost", 8765), _Handler)
    server._done = False
    while not server._done:
        server.handle_request()
    server.server_close()

    if _result.get("error"):
        print(f"ERROR: {_result['error']}"); sys.exit(1)

    code     = _result["code"]
    realm_id = _result["realmId"]
    print(f"REALM_ID: {realm_id}")

    encoded = base64.b64encode(f"{creds['client_id']}:{creds['client_secret']}".encode()).decode()
    resp = requests.post(
        TOKEN_URL,
        headers={"Authorization": f"Basic {encoded}", "Accept": "application/json",
                 "Content-Type": "application/x-www-form-urlencoded"},
        data={"grant_type": "authorization_code", "code": code, "redirect_uri": REDIRECT_URI},
        timeout=30,
    )
    resp.raise_for_status()
    tokens = resp.json()

    creds.setdefault("companies", {})[name] = {
        "realm_id":      realm_id,
        "env":           company["env"],
        "access_token":  tokens.get("access_token"),
        "refresh_token": tokens.get("refresh_token"),
        "token_type":    tokens.get("token_type", "Bearer"),
    }
    CREDENTIALS_FILE.write_text(json.dumps(creds, indent=2))
    CREDENTIALS_FILE.chmod(0o600)
    print(f"SAVED: {name}")

if __name__ == "__main__":
    main()
