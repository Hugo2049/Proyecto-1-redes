"""Thin wrapper around the Anthropic Messages API.

This is the "talk to an LLM at the API level" piece (requirement #1). Tool
definitions collected from the connected MCP servers are translated into the
shape the Messages API expects and passed on every call so the model can
decide when to invoke them.
"""

from __future__ import annotations

import os

from anthropic import Anthropic
from anthropic.types import Message

DEFAULT_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-5")
MAX_TOKENS = 1536

BASE_SYSTEM_PROMPT = (
    "You are a helpful assistant running in a terminal chatbot for a networking "
    "class project. You have access to tools exposed by MCP (Model Context "
    "Protocol) servers: a clinic appointment system, a sandboxed filesystem, "
    "and git. Use them whenever the user's request requires real-world state "
    "or actions instead of guessing. Be concise."
)


class LLMClient:
    def __init__(
        self,
        api_key: str | None = None,
        model: str = DEFAULT_MODEL,
        system_prompt: str = BASE_SYSTEM_PROMPT,
    ) -> None:
        api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY is not set. Create an Anthropic API key and "
                "export it (or put it in chatbot/.env) before running the chatbot."
            )
        self._client = Anthropic(api_key=api_key)
        self.model = model
        self.system_prompt = system_prompt

    def send(self, messages: list[dict], tools: list[dict]) -> Message:
        return self._client.messages.create(
            model=self.model,
            max_tokens=MAX_TOKENS,
            system=self.system_prompt,
            messages=messages,
            tools=tools,
        )
