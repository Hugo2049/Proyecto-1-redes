"""Registry of MCP servers the chatbot host connects to.

Each entry maps to one subprocess speaking JSON-RPC 2.0 over stdio. Servers
can be toggled off with an environment variable in case a machine is missing
a required runtime (Node.js for the filesystem server, uv/uvx for the git
and clinic servers).
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from chatbot.mcp_client import MCPServerConfig

REPO_ROOT = Path(__file__).resolve().parents[3]
CLINIC_SERVER_DIR = REPO_ROOT / "mcp_server_v1"

# Sandbox directory exposed to the Filesystem and Git MCP servers, so a demo
# ("create a repo, add a README, commit it") does not touch the rest of the
# project. Override with MCP_WORKSPACE_DIR if you want a different folder.
WORKSPACE_DIR = Path(os.environ.get("MCP_WORKSPACE_DIR", REPO_ROOT / "chatbot" / "workspace"))


def _env_enabled(var: str, default: bool = True) -> bool:
    value = os.environ.get(var)
    if value is None:
        return default
    return value.strip().lower() not in {"0", "false", "no"}


def _ensure_git_repo(path: Path) -> None:
    """`mcp-server-git` refuses to start if --repository is not already a Git
    repo (it has no `git_init` tool to create one), so the host provisions an
    empty repo once. The chatbot-driven demo still covers creating the README
    (filesystem server) and staging/committing it (git server) end to end.
    """
    if (path / ".git").exists():
        return
    subprocess.run(["git", "init", str(path)], capture_output=True, check=False)


DEFAULT_CLINIC_REMOTE_URL = "https://clinic-appointment-mcp-remote.hugomcp.workers.dev/"


class HttpServerConfig:
    def __init__(self, id: str, url: str, enabled: bool, description: str = "") -> None:
        self.id = id
        self.url = url
        self.enabled = enabled
        self.description = description


def load_http_server_configs() -> list[HttpServerConfig]:
    return [
        HttpServerConfig(
            id="clinic_remote",
            url=os.environ.get("CLINIC_REMOTE_URL", DEFAULT_CLINIC_REMOTE_URL),
            enabled=_env_enabled("CHATBOT_ENABLE_CLINIC_REMOTE", default=False),
            description="Clinic Appointment MCP server, deployed remotely on Cloudflare Workers.",
        ),
    ]


def load_server_configs() -> list[MCPServerConfig]:
    WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)
    _ensure_git_repo(WORKSPACE_DIR)

    return [
        MCPServerConfig(
            id="clinic",
            command=["uv", "run", "--directory", str(CLINIC_SERVER_DIR), "main.py"],
            enabled=_env_enabled("CHATBOT_ENABLE_CLINIC"),
            description="Custom local MCP server: clinic appointment management.",
        ),
        MCPServerConfig(
            id="filesystem",
            command=["npx", "-y", "@modelcontextprotocol/server-filesystem", str(WORKSPACE_DIR)],
            enabled=_env_enabled("CHATBOT_ENABLE_FILESYSTEM"),
            description="Official MCP filesystem server, sandboxed to the workspace folder.",
        ),
        MCPServerConfig(
            id="git",
            command=["uvx", "--native-tls", "mcp-server-git", "--repository", str(WORKSPACE_DIR)],
            enabled=_env_enabled("CHATBOT_ENABLE_GIT"),
            description="Official MCP git server, operating on the workspace folder.",
        ),
    ]
