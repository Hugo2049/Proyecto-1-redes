"""Generic MCP client: talks JSON-RPC 2.0 over stdio to a spawned server process.

Implemented by hand (no MCP SDK), as required by the project statement. It
works against any spec-compliant MCP server over stdio, whether that is our
own Clinic Appointment server or an official server such as
``@modelcontextprotocol/server-filesystem`` or ``mcp-server-git``.
"""

from __future__ import annotations

import itertools
import json
import shutil
import subprocess
import threading
from dataclasses import dataclass, field

from chatbot.logging_util import MCPLogger

PROTOCOL_VERSION = "2025-11-25"
CLIENT_NAME = "cc3067-chatbot-host"
CLIENT_VERSION = "0.1.0"


class MCPError(Exception):
    """Raised when a server returns a JSON-RPC error for a request."""


@dataclass
class MCPServerConfig:
    id: str
    command: list[str]
    cwd: str | None = None
    enabled: bool = True
    description: str = ""


@dataclass
class MCPTool:
    server_id: str
    name: str
    description: str
    input_schema: dict
    qualified_name: str = field(init=False)

    def __post_init__(self) -> None:
        self.qualified_name = f"{self.server_id}__{self.name}"


class MCPClient:
    """Owns one MCP server subprocess and its JSON-RPC session."""

    def __init__(self, config: MCPServerConfig, logger: MCPLogger) -> None:
        self.config = config
        self.logger = logger
        self._process: subprocess.Popen | None = None
        self._id_counter = itertools.count(1)
        self.tools: list[MCPTool] = []

    # -- process lifecycle ---------------------------------------------
    def start(self) -> None:
        argv = list(self.config.command)
        resolved = shutil.which(argv[0])
        if resolved:
            argv[0] = resolved
        self._process = subprocess.Popen(
            argv,
            cwd=self.config.cwd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        threading.Thread(target=self._drain_stderr, daemon=True).start()
        self._initialize()
        self.tools = self._list_tools()

    def _drain_stderr(self) -> None:
        assert self._process is not None and self._process.stderr is not None
        for line in self._process.stderr:
            line = line.rstrip()
            if line:
                self.logger.info(f"[{self.config.id}][stderr] {line}")

    def close(self) -> None:
        if self._process is None:
            return
        try:
            self._process.stdin.close()
        except Exception:
            pass
        try:
            self._process.terminate()
            self._process.wait(timeout=5)
        except Exception:
            self._process.kill()

    # -- JSON-RPC plumbing -----------------------------------------------
    def _send(self, message: dict) -> None:
        assert self._process is not None and self._process.stdin is not None
        self.logger.request(self.config.id, message)
        self._process.stdin.write(json.dumps(message) + "\n")
        self._process.stdin.flush()

    def _read_message(self) -> dict:
        assert self._process is not None and self._process.stdout is not None
        while True:
            line = self._process.stdout.readline()
            if line == "":
                raise MCPError(f"Server '{self.config.id}' closed its stdout unexpectedly")
            line = line.strip()
            if not line:
                continue
            return json.loads(line)

    def _request(self, method: str, params: dict | None = None) -> dict:
        request_id = next(self._id_counter)
        self._send({"jsonrpc": "2.0", "id": request_id, "method": method, "params": params or {}})
        while True:
            message = self._read_message()
            if message.get("id") == request_id:
                self.logger.response(self.config.id, message)
                if "error" in message:
                    raise MCPError(message["error"].get("message", "unknown error"))
                return message.get("result", {})
            # Notification or unrelated message from the server: log and keep waiting.
            self.logger.response(self.config.id, message)

    def _notify(self, method: str, params: dict | None = None) -> None:
        self._send({"jsonrpc": "2.0", "method": method, "params": params or {}})

    # -- MCP protocol methods --------------------------------------------
    def _initialize(self) -> None:
        self._request(
            "initialize",
            {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": CLIENT_NAME, "version": CLIENT_VERSION},
            },
        )
        self._notify("notifications/initialized")

    def _list_tools(self) -> list[MCPTool]:
        result = self._request("tools/list")
        return [
            MCPTool(
                server_id=self.config.id,
                name=t["name"],
                description=t.get("description", ""),
                input_schema=t.get("inputSchema", {"type": "object", "properties": {}}),
            )
            for t in result.get("tools", [])
        ]

    def call_tool(self, name: str, arguments: dict) -> dict:
        return self._request("tools/call", {"name": name, "arguments": arguments})
