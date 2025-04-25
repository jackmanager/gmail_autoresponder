"""
app/gmail_service.py

Gmail Service – typed wrapper around the Gmail API v1 (google-api-python-client)
Includes helpers to:
  • extract a clean body from a Gmail message (strip_quotes)
  • build a MIME reply (build_mime)
  • create / update / send / delete drafts, mark messages read, list unread

Fully compatible with Python 3.13 and open-source libraries pinned in requirements.txt.
"""

from __future__ import annotations

import base64
import html
import os
import re
from email.mime.text import MIMEText
from pathlib import Path
from typing import Dict, List, Optional

from bs4 import BeautifulSoup
from dotenv import load_dotenv
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# ─────────────────────────── env vars ────────────────────────────────
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

GOOGLE_CLIENT_ID     = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
GMAIL_REFRESH_TOKEN  = os.getenv("GMAIL_REFRESH_TOKEN")

if not (GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET and GMAIL_REFRESH_TOKEN):
    raise RuntimeError("Missing Gmail OAuth credentials in .env")

# ────────────────────────── helpers ─────────────────────────────────

def _b64decode_url(data: str) -> str:
    """URL-safe base-64 decode that tolerates missing padding."""
    if not data:
        return ""
    data += "=" * (-len(data) % 4)  # right-pad to 4-byte boundary
    try:
        return base64.urlsafe_b64decode(data).decode("utf-8", "ignore")
    except Exception:
        return ""


def strip_quotes(message: Dict) -> str:
    """Return the cleaned text of a Gmail *message* (remove quoted history)."""
    payload = message.get("payload", {})
    parts   = payload.get("parts", [])[:]

    text_part, html_part = "", ""
    while parts:
        p     = parts.pop()
        mtype = p.get("mimeType", "")
        if mtype.startswith("multipart/"):
            parts.extend(p.get("parts", []))
        elif mtype == "text/plain":
            text_part += _b64decode_url(p.get("body", {}).get("data", ""))
        elif mtype == "text/html":
            html_part += _b64decode_url(p.get("body", {}).get("data", ""))

    body = text_part or html_part or message.get("snippet", "")
    if html_part and not text_part:
        body = html.unescape(BeautifulSoup(body, "html.parser").get_text(" ", strip=True))

    cleaned: List[str] = []
    for line in body.splitlines():
        if re.match(r"^>+|\s*On .*wrote:", line):
            break  # stop at first quoted section
        cleaned.append(line.rstrip())

    return "\n".join(cleaned).strip() or body.strip()


def build_mime(reply_text: str, original: Dict, from_addr: str) -> str:
    """Return base-64url-encoded RFC 822 message suitable for Gmail `raw`."""
    hdrs  = {h["name"].lower(): h["value"] for h in original.get("payload", {}).get("headers", [])}
    to    = hdrs.get("from")
    subj  = hdrs.get("subject", "").strip()
    mid   = hdrs.get("message-id")

    if not to:
        raise ValueError("Original message lacks 'From' header – cannot reply")
    if not subj.lower().startswith("re:"):
        subj = f"Re: {subj or 'your email'}"

    msg             = MIMEText(reply_text, _charset="utf-8")
    msg["To"]        = to
    msg["From"]      = from_addr
    msg["Subject"]   = subj
    if mid:
        msg["In-Reply-To"] = mid
        msg["References"]  = mid

    return base64.urlsafe_b64encode(msg.as_bytes()).decode("utf-8")

# ───────────────────── GmailService class ───────────────────────────
class GmailService:
    """Thin convenience wrapper around the Gmail API."""

    def __init__(self) -> None:
        creds = Credentials(
            None,
            refresh_token=GMAIL_REFRESH_TOKEN,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=GOOGLE_CLIENT_ID,
            client_secret=GOOGLE_CLIENT_SECRET,
        )
        creds.refresh(Request())
        self.service = build("gmail", "v1", credentials=creds, cache_discovery=False)

        prof = self.service.users().getProfile(userId="me").execute()
        self.user_email: str = prof.get("emailAddress", "me")

    # ─────────── low-level Gmail operations ────────────
    def list_unread(self, max_results: int = 50) -> List[Dict]:
        try:
            resp = (
                self.service.users()
                .messages()
                .list(userId="me", labelIds=["INBOX", "UNREAD"], maxResults=max_results)
                .execute()
            )
            return resp.get("messages", []) or []
        except HttpError as exc:
            print("[gmail] list_unread error:", exc)
            return []

    def get_message(self, msg_id: str) -> Dict:
        return self.service.users().messages().get(userId="me", id=msg_id, format="full").execute()

    # ─────────── draft helpers ────────────
    def create_draft(self, raw: str, thread_id: Optional[str] = None) -> Dict:
        if not raw:
            raise ValueError("create_draft: raw payload is empty")
        body: Dict = {"message": {"raw": raw}}
        if thread_id:
            body["message"]["threadId"] = thread_id
        return self.service.users().drafts().create(userId="me", body=body).execute()

    def update_draft(self, draft_id: str, new_text: str) -> Dict:
        """Replace the body of an existing draft with *new_text* (plain text)."""
        # 1) fetch current draft to reuse headers
        draft   = self.service.users().drafts().get(userId="me", id=draft_id).execute()
        message = draft["message"]
        hdrs    = {h["name"].lower(): h["value"] for h in message["payload"]["headers"]}
        to      = hdrs.get("to", hdrs.get("from", ""))
        subj    = hdrs.get("subject", "Re:")

        mime            = MIMEText(new_text, _charset="utf-8")
        mime["To"]       = to
        mime["Subject"]  = subj
        raw             = base64.urlsafe_b64encode(mime.as_bytes()).decode("utf-8")

        body = {"id": draft_id, "message": {"raw": raw}}
        return self.service.users().drafts().update(userId="me", id=draft_id, body=body).execute()

    def send_draft(self, draft_id: str) -> Dict:
        return self.service.users().drafts().send(userId="me", body={"id": draft_id}).execute()

    def delete_draft(self, draft_id: str) -> None:
        self.service.users().drafts().delete(userId="me", id=draft_id).execute()

    # ─────────── misc helpers ────────────
    def mark_read(self, msg_id: str) -> None:
        self.service.users().messages().modify(userId="me", id=msg_id, body={"removeLabelIds": ["UNREAD"]}).execute()
