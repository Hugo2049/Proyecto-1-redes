"""MCP client for servers reachable over HTTP instead of stdio.

Used for the remote Cloudflare Workers deployment of the Clinic Appointment
server (functionality #6: same server, different transport). The JSON-RPC
2.0 message shapes are identical to the stdio client in mcp_client.py; only
the transport changes (one HTTP POST per message instead of newline-
delimited stdin/stdout).

Two real-world networking issues showed up while testing this against
Cloudflare Workers and are worked around here:
  - This machine's network path does TLS interception that occasionally
    produces malformed certificates. `truststore` makes Python validate
    against the OS certificate store (the one the browser already trusts)
    instead of the bundled certifi list, and a short retry absorbs the
    handful of connections that still glitch.
  - Cloudflare's edge appears to reject requests from an unrecognized/empty
    User-Agent on workers.dev subdomains, so a normal browser UA is sent.
"""

from __future__ import annotations

import itertools
import json
import ssl
import time
import urllib.error
import urllib.request

import truststore

from chatbot.logging_util import MCPLogger
from chatbot.mcp_client import CLIENT_NAME, CLIENT_VERSION, PROTOCOL_VERSION, MCPError, MCPTool

_SSL_CONTEXT = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0 Safari/537.36 cc3067-chatbot-host"
)


class MCPHttpClient:
    """Same public interface as MCPClient (start/close/tools/call_tool)."""

    def __init__(self, server_id: str, url: str, logger: MCPLogger, retries: int = 4) -> None:
        self.server_id = server_id
        self.url = url
        self.logger = logger
        self.retries = retries
        self._id_counter = itertools.count(1)
        self.tools: list[MCPTool] = []

    def start(self) -> None:
        self._request(
            "initialize",
            {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": CLIENT_NAME, "version": CLIENT_VERSION},
            },
        )
        self._notify("notifications/initialized")
        result = self._request("tools/list")
        self.tools = [
            MCPTool(
                server_id=self.server_id,
                name=t["name"],
                description=t.get("description", ""),
                input_schema=t.get("inputSchema", {"type": "object", "properties": {}}),
            )
            for t in result.get("tools", [])
        ]

    def close(self) -> None:
        pass  # stateless HTTP, nothing to tear down

    def _post(self, message: dict) -> dict | None:
        body = json.dumps(message).encode("utf-8")
        last_exc: Exception | None = None
        for attempt in range(self.retries):
            req = urllib.request.Request(
                self.url,
                data=body,
                headers={"Content-Type": "application/json", "User-Agent": USER_AGENT},
                method="POST",
            )
            try:
                with urllib.request.urlopen(req, timeout=15, context=_SSL_CONTEXT) as resp:
                    raw = resp.read()
                    return json.loads(raw) if raw else None
            except urllib.error.HTTPError as exc:
                last_exc = exc
            except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
                last_exc = exc
            time.sleep(1.5 * (attempt + 1))
        raise MCPError(f"HTTP request to '{self.server_id}' failed after {self.retries} attempts: {last_exc}")

    def _request(self, method: str, params: dict | None = None) -> dict:
        request_id = next(self._id_counter)
        message = {"jsonrpc": "2.0", "id": request_id, "method": method, "params": params or {}}
        self.logger.request(self.server_id, message)
        response = self._post(message)
        if response is None:
            raise MCPError(f"No response from '{self.server_id}' for method '{method}'")
        self.logger.response(self.server_id, response)
        if "error" in response:
            raise MCPError(response["error"].get("message", "unknown error"))
        return response.get("result", {})

    def _notify(self, method: str, params: dict | None = None) -> None:
        message = {"jsonrpc": "2.0", "method": method, "params": params or {}}
        self.logger.request(self.server_id, message)
        self._post(message)

    def call_tool(self, name: str, arguments: dict) -> dict:
        return self._request("tools/call", {"name": name, "arguments": arguments})
