"""Optional web UI backend, this is the extra credit User Interface piece.

Reuses the exact same ChatSession the console REPL uses in app.py, the web
page just replaces the terminal as the transport, one HTTP POST per message
instead of stdin, the MCP wiring, logging, and tool routing underneath stay
the same.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from chatbot.app import ChatSession

REPO_ROOT = Path(__file__).resolve().parents[3]
FRONTEND_DIR = REPO_ROOT / "frontend"

app = FastAPI(title="Clinic Assistant")
session: ChatSession | None = None


class ChatRequest(BaseModel):
    message: str


@app.on_event("startup")
def _startup() -> None:
    global session
    session = ChatSession()


@app.on_event("shutdown")
def _shutdown() -> None:
    if session is not None:
        session.close()


@app.get("/api/tools")
def list_tools() -> list[dict]:
    assert session is not None
    return [
        {"id": t.qualified_name, "server": t.server_id, "name": t.name, "description": t.description}
        for t in session.tools
    ]


@app.get("/api/servers")
def list_servers() -> list[str]:
    assert session is not None
    return list(session.manager.clients)


@app.post("/api/chat")
def chat(req: ChatRequest) -> dict:
    assert session is not None
    return session.send(req.message)


# Registered last: everything not matched by an /api/* route above falls
# through to the static frontend, and "/" serves frontend/index.html.
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
