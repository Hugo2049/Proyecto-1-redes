"""Chatbot host: console REPL that talks to an LLM and routes tool calls to MCP servers.

Covers requirements #1-#3 of the project statement:
  1) talks to the Anthropic API directly (chatbot.llm.LLMClient)
  2) keeps conversation context across turns (the `messages` list below)
  3) logs every MCP request/response (chatbot.logging_util.MCPLogger)
"""

from __future__ import annotations

from chatbot.config import WORKSPACE_DIR, load_http_server_configs, load_server_configs
from chatbot.llm import BASE_SYSTEM_PROMPT, LLMClient
from chatbot.logging_util import MCPLogger
from chatbot.mcp_client import MCPClient, MCPError, MCPTool
from chatbot.mcp_http_client import MCPHttpClient

EXIT_WORDS = {"salir", "exit", "quit"}


class ServerManager:
    def __init__(self, logger: MCPLogger) -> None:
        self.logger = logger
        self.clients: dict[str, MCPClient | MCPHttpClient] = {}

    def connect_all(self) -> None:
        for cfg in load_server_configs():
            if not cfg.enabled:
                self.logger.info(f"server '{cfg.id}' disabled via env var, skipping")
                continue
            self._connect(cfg.id, MCPClient(cfg, self.logger))

        for cfg in load_http_server_configs():
            if not cfg.enabled:
                self.logger.info(f"server '{cfg.id}' disabled via env var, skipping")
                continue
            self._connect(cfg.id, MCPHttpClient(cfg.id, cfg.url, self.logger))

    def _connect(self, server_id: str, client: MCPClient | MCPHttpClient) -> None:
        try:
            client.start()
        except Exception as exc:  # noqa: BLE001 - degrade gracefully, don't crash the chatbot
            self.logger.info(f"could not start server '{server_id}': {exc}")
            return
        self.clients[server_id] = client
        self.logger.info(f"connected '{server_id}' with {len(client.tools)} tool(s)")

    def all_tools(self) -> list[MCPTool]:
        return [tool for client in self.clients.values() for tool in client.tools]

    def call(self, qualified_name: str, arguments: dict) -> dict:
        server_id, _, tool_name = qualified_name.partition("__")
        client = self.clients.get(server_id)
        if client is None:
            raise MCPError(f"Unknown or disconnected server for tool '{qualified_name}'")
        return client.call_tool(tool_name, arguments)

    def close_all(self) -> None:
        for client in self.clients.values():
            client.close()


def _anthropic_tools(tools: list[MCPTool]) -> list[dict]:
    return [
        {"name": t.qualified_name, "description": t.description, "input_schema": t.input_schema}
        for t in tools
    ]


def _tool_result_text(result: dict) -> str:
    parts = [block.get("text", "") for block in result.get("content", []) if block.get("type") == "text"]
    return "\n".join(parts) if parts else str(result)


def _build_system_prompt() -> str:
    return (
        f"{BASE_SYSTEM_PROMPT}\n\n"
        f"The git and filesystem tools are sandboxed to this folder: {WORKSPACE_DIR}. "
        f"A Git repository already exists at the root of that folder (there is no "
        f"git_init tool available, so never try to create a new repo in a subfolder). "
        f"When the user asks to 'create a repository', treat the existing repo at "
        f"{WORKSPACE_DIR} as that repository and use this exact path as repo_path for "
        f"every git_* tool call."
    )


class ChatSession:
    """One conversation with the LLM plus every MCP server it can call.

    Shared by the console REPL (``run`` below) and the optional web UI
    (``chatbot.webserver``), so both interfaces exercise the exact same MCP
    wiring, logging, and tool-use loop, only the transport around ``send``
    differs.
    """

    def __init__(self) -> None:
        # Fail fast on a missing API key before spawning any MCP subprocess.
        self.llm = LLMClient(system_prompt=_build_system_prompt())
        self.logger = MCPLogger()
        self.manager = ServerManager(self.logger)
        self.manager.connect_all()
        self.tools = self.manager.all_tools()
        self._tools_payload = _anthropic_tools(self.tools)
        self.messages: list[dict] = []

    def send(self, user_text: str) -> dict:
        """Run one turn: send `user_text`, resolve any tool calls, return the reply."""
        self.messages.append({"role": "user", "content": user_text})
        response = self.llm.send(self.messages, self._tools_payload)

        tool_calls: list[dict] = []
        while response.stop_reason == "tool_use":
            self.messages.append({"role": "assistant", "content": response.content})
            tool_results = []
            for block in response.content:
                if block.type != "tool_use":
                    continue
                try:
                    result = self.manager.call(block.name, block.input)
                    text = _tool_result_text(result)
                    is_error = False
                except MCPError as exc:
                    text = str(exc)
                    is_error = True
                tool_result: dict = {"type": "tool_result", "tool_use_id": block.id, "content": text}
                if is_error:
                    tool_result["is_error"] = True
                tool_results.append(tool_result)
                tool_calls.append({"tool": block.name, "input": block.input, "output": text, "error": is_error})
            self.messages.append({"role": "user", "content": tool_results})
            response = self.llm.send(self.messages, self._tools_payload)

        self.messages.append({"role": "assistant", "content": response.content})
        final_text = "\n".join(b.text for b in response.content if b.type == "text")
        return {"reply": final_text, "tool_calls": tool_calls}

    def close(self) -> None:
        self.manager.close_all()
        self.logger.close()


def run() -> None:
    try:
        session = ChatSession()
    except RuntimeError as exc:
        print(f"Cannot start chatbot: {exc}")
        return

    print(f"Connected MCP servers: {', '.join(session.manager.clients) or '(none)'}")
    print(f"Available tools: {', '.join(t.qualified_name for t in session.tools) or '(none)'}")
    print("Type 'exit' to quit.\n")

    try:
        while True:
            try:
                user_input = input("You: ").strip()
            except EOFError:
                break
            if not user_input:
                continue
            if user_input.lower() in EXIT_WORDS:
                break

            result = session.send(user_input)
            print(f"Assistant: {result['reply']}\n")
    except KeyboardInterrupt:
        print()
    finally:
        session.close()
