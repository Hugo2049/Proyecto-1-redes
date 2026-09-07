"""Logging of every JSON-RPC exchange between the chatbot host and the MCP servers.

Satisfies requirement #3 of the project statement: keep and display a log of
all requests/responses exchanged with MCP servers. Every message is printed
to the console (so it is visible live during a demo) and also appended to a
timestamped file under ``logs/`` for later inspection / the written report.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

LOGS_DIR = Path(__file__).resolve().parent.parent.parent / "logs"


class MCPLogger:
    def __init__(self, log_file: Path | None = None) -> None:
        LOGS_DIR.mkdir(exist_ok=True)
        self.log_file = log_file or LOGS_DIR / f"mcp_{datetime.now():%Y%m%d_%H%M%S}.log"
        self._fh = open(self.log_file, "a", encoding="utf-8")

    def _write(self, line: str) -> None:
        print(line, file=sys.stderr, flush=True)
        self._fh.write(line + "\n")
        self._fh.flush()

    def request(self, server_id: str, message: dict) -> None:
        method = message.get("method", "?")
        self._write(f"[{_ts()}] [{server_id}] --> {method} {json.dumps(message, ensure_ascii=False)}")

    def response(self, server_id: str, message: dict) -> None:
        if "error" in message:
            summary = f"ERROR {message['error']}"
        else:
            summary = "OK"
        self._write(f"[{_ts()}] [{server_id}] <-- {summary} {json.dumps(message, ensure_ascii=False)}")

    def info(self, text: str) -> None:
        self._write(f"[{_ts()}] [host] {text}")

    def close(self) -> None:
        self._fh.close()


def _ts() -> str:
    return datetime.now().strftime("%H:%M:%S")
