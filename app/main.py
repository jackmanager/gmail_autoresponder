"""
app/main.py  –  FastAPI UI for Gmail-autoresponder
Option A: no DB migration, shows Subject · From · Body · Reply · Sent Response.
Flash banners after actions; buttons vanish once a draft is processed.
Brace-safe for Python 3.13.
"""

# ── 0 · env ───────────────────────────────────────────────────────────
from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv())

# ── 1 · std-lib / third-party ─────────────────────────────────────────
import os, secrets, html, re
from datetime import datetime
from typing import List, Dict

from fastapi import FastAPI, Depends, HTTPException, status, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from starlette.middleware.sessions import SessionMiddleware

# ── 2 · internal modules ──────────────────────────────────────────────
from .gmail_service   import GmailService, strip_quotes
from .draft_repo      import DraftRepository
from .scheduler       import SchedulerService

# ── 3 · app + session cookie ─────────────────────────────────────────
app = FastAPI(title="Gmail Auto-responder")
app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("SESSION_SECRET", secrets.token_urlsafe(32)),
)

# ── 4 · BASIC-AUTH (single admin) ────────────────────────────────────
security      = HTTPBasic()
AUTH_USERNAME = os.getenv("AUTH_USERNAME", "admin")
AUTH_PASSWORD = os.getenv("AUTH_PASSWORD", "password")

def verify(creds: HTTPBasicCredentials = Depends(security)) -> str:
    if not (
        secrets.compare_digest(creds.username, AUTH_USERNAME)
        and secrets.compare_digest(creds.password,  AUTH_PASSWORD)
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Basic"},
        )
    return creds.username

# ── 5 · singletons ───────────────────────────────────────────────────
gmail = GmailService()
db    = DraftRepository()
sched = SchedulerService()

# ── 6 · lifecycle ────────────────────────────────────────────────────
@app.on_event("startup")
async def _start(): sched.start()

@app.on_event("shutdown")
async def _stop():  sched.shutdown()

# ── 7 · helper – build <table> HTML ──────────────────────────────────
def build_table(rows: List[Dict]) -> str:
    if not rows:
        return (
            '<div class="empty-state"><h2>No drafts</h2>'
            '<p>Check back later for new email drafts.</p></div>'
        )

    def mk_row(d: Dict) -> str:
        created   = datetime.fromisoformat(d["created_at"]).strftime("%Y-%m-%d&nbsp;%H:%M")
        subj      = html.escape(d["subject"])
        sender    = html.escape(d["from"])
        body_pv   = html.escape(d["body"][:120]  + ("…" if len(d["body"])  > 120 else ""))
        reply_pv  = html.escape(d["reply_text"][:120] + "…")
        sent_pv   = reply_pv if d["status"].startswith("sent") else ""
        reply_js  = html.escape(d["reply_text"]).replace("`", "\\`")
        did       = d["id"]

        actions = ""
        if d["status"] == "pending":
            actions = (
                f"<form method='POST' action='/drafts/{did}/send' style='display:inline'>"
                f"<button class='btn btn-send'>Send</button></form>"
                f"<button class='btn btn-edit' onclick=\"openEditModal('{did}', `{reply_js}`)\">Edit&nbsp;&amp;&nbsp;Send</button>"
                f"<form method='POST' action='/drafts/{did}/reject' style='display:inline'>"
                f"<button class='btn btn-reject'>Reject</button></form>"
            )

        return (
            f"<tr>"
            f"<td>{did}</td><td>{created}</td><td>{sender}</td><td>{subj}</td>"
            f"<td>{body_pv}</td><td>{reply_pv}</td><td>{sent_pv}</td>"
            f"<td class='actions'>{actions}</td></tr>"
        )

    head = (
        "<table><thead><tr>"
        "<th>ID</th><th>Created</th><th>From</th><th>Subject</th>"
        "<th>Original&nbsp;Body</th><th>Reply Draft</th><th>Sent&nbsp;Response</th><th>Actions</th>"
        "</tr></thead><tbody>"
    )
    return head + "".join(mk_row(r) for r in rows) + "</tbody></table>"

# ── 8 · /drafts page ─────────────────────────────────────────────────
@app.get("/drafts", response_class=HTMLResponse)
async def drafts_page(request: Request, _: str = Depends(verify)):
    rows = db.get_all_drafts(limit=100)

    # enrich Subject / From / Body for UI
    for r in rows:
        msg       = gmail.get_message(r["message_id"])
        headers   = {h["name"].lower(): h["value"] for h in msg["payload"]["headers"]}
        r["subject"] = headers.get("subject", "(no subject)")
        r["from"]    = re.sub(r"[<>]", "", headers.get("from", ""))   # strip <addr>
        r["body"]    = strip_quotes(msg)

    banner = {
        "sent":      "<div class='flash ok'>Draft sent successfully.</div>",
        "sent_edit": "<div class='flash ok'>Edited draft sent successfully.</div>",
        "rejected":  "<div class='flash warn'>Draft rejected.</div>",
    }.get(request.query_params.get("msg"), "")

    html_doc = f"""<!DOCTYPE html>
<html><head>
<meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>
<title>Drafts – Gmail Auto-responder</title>
<style>
 body{{font-family:Arial,sans-serif;margin:0;padding:20px;}}
 table{{width:100%;border-collapse:collapse;margin-top:20px;}}
 th,td{{padding:12px 14px;border-bottom:1px solid #ddd;text-align:left;}}
 th{{background:#f2f2f2;}} tr:hover{{background:#f5f5f5;}}
 .actions{{display:flex;gap:8px;}}
 .btn{{padding:8px 12px;border:none;border-radius:4px;font-size:14px;cursor:pointer;}}
 .btn-send{{background:#4caf50;color:#fff;}} .btn-edit{{background:#2196f3;color:#fff;}} .btn-reject{{background:#f44336;color:#fff;}}
 .flash{{padding:12px;border-radius:4px;margin-top:12px;font-weight:bold;}}
 .flash.ok{{background:#e8f5e9;color:#1b5e20;border:1px solid #1b5e20;}}
 .flash.warn{{background:#ffebee;color:#b71c1c;border:1px solid #b71c1c;}}
 .modal{{display:none;position:fixed;z-index:1;left:0;top:0;width:100%;height:100%;background:rgba(0,0,0,.4);}}
 .modal-content{{background:#fff;margin:5% auto;padding:20px;border:1px solid #888;width:90%;max-width:700px;border-radius:5px;}}
 .close{{float:right;font-size:28px;font-weight:bold;color:#aaa;cursor:pointer;}} .close:hover{{color:#000;}}
 textarea{{width:100%;height:220px;padding:10px;border:1px solid #ccc;border-radius:4px;font-family:Arial;font-size:14px;resize:vertical;}}
 .modal-actions{{margin-top:15px;text-align:right;}}
</style>
</head><body>
<h1>Drafts</h1>{banner}{build_table(rows)}
<div id='editModal' class='modal'><div class='modal-content'>
  <span class='close' onclick='closeEditModal()'>&times;</span>
  <h2>Edit Reply</h2>
  <form id='editForm' method='POST' action=''>
    <textarea id='editText' name='edited_text'></textarea>
    <div class='modal-actions'><button class='btn btn-send'>Send Edited Reply</button></div>
  </form>
</div></div>
<script>
 const modal=document.getElementById('editModal');
 const editForm=document.getElementById('editForm');
 const editText=document.getElementById('editText');
 function openEditModal(id,text) {{
   const draftId=parseInt(id,10);
   editForm.action='/drafts/'+draftId+'/send_with_body';
   editText.value=text;
   modal.style.display='block';
 }}
 function closeEditModal() {{ modal.style.display='none'; }}
 window.onclick=(e)=>{{ if(e.target===modal) closeEditModal(); }};
</script>
</body></html>"""

    return HTMLResponse(html_doc)

# ── 9 · root & endpoints ─────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
async def root(_: str = Depends(verify)):
    return RedirectResponse("/drafts")

@app.post("/drafts/{db_id}/send")
async def send(db_id: int, _: str = Depends(verify)):
    d = db.get_draft(db_id) or HTTPException(404, "Not found")
    gmail.send_draft(d["draft_id"])
    db.update_draft_status(db_id, "sent_no_edit")
    return RedirectResponse("/drafts?msg=sent", status_code=303)

@app.post("/drafts/{db_id}/send_with_body")
async def send_edit(db_id: int, edited_text: str = Form(...), _: str = Depends(verify)):
    d = db.get_draft(db_id) or HTTPException(404, "Not found")
    gmail.update_draft(d["draft_id"], edited_text)
    gmail.send_draft(d["draft_id"])
    db.update_draft_status(db_id, "sent_with_edit", edited_text)
    return RedirectResponse("/drafts?msg=sent_edit", status_code=303)

@app.post("/drafts/{db_id}/reject")
async def reject(db_id: int, _: str = Depends(verify)):
    if not db.update_draft_status(db_id, "rejected"):
        raise HTTPException(404, "Draft not found")
    return RedirectResponse("/drafts?msg=rejected", status_code=303)
