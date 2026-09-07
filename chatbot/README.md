# Chatbot Host

This is a console chatbot that talks to the Anthropic API and uses MCP, which stands for Model Context Protocol, servers as tools. This is the host part of the project, it finds the tools that each MCP server offers, shows them to the LLM, and runs whichever tool the model decides to call.

The MCP side of the transport, meaning `initialize`, `notifications/initialized`, `tools/list` and `tools/call`, framed as JSON-RPC 2.0 over stdio, is written by hand in [`src/chatbot/mcp_client.py`](src/chatbot/mcp_client.py), no MCP SDK is used, since the assignment asks for that. The only SDK used is the official Anthropic SDK, and that is allowed, since it does not implement MCP, it just talks to the LLM.

## What it does

- Talks to an LLM at the API level, using the Anthropic Messages API, including tool use, see [`src/chatbot/llm.py`](src/chatbot/llm.py).
- Keeps conversation context, the full message history, including tool calls and their results, stays in memory and gets sent again on every turn, so a follow up question like "when was he born" after "who was Alan Turing" gets answered correctly.
- Logs every MCP request and response, live on the console and also saved to `logs/mcp_<timestamp>.log`, see [`src/chatbot/logging_util.py`](src/chatbot/logging_util.py).
- Connects to MCP servers over both stdio and HTTP:

  | id | server | transport | purpose |
  |---|---|---|---|
  | `clinic` | our own [`mcp_server_v1`](../mcp_server_v1) | stdio | Clinic Appointment MCP Server, custom, manual JSON-RPC, local |
  | `filesystem` | official `@modelcontextprotocol/server-filesystem` | stdio | file operations, sandboxed inside `chatbot/workspace/` |
  | `git` | official `mcp-server-git` | stdio | git operations inside `chatbot/workspace/` |
  | `clinic_remote` | our own [`mcp_server_remote`](../mcp_server_remote) | HTTP | the same clinic server, deployed on Cloudflare Workers, off by default, see below |

  Tool names are namespaced as `<server_id>__<tool_name>`, for example `clinic__book_appointment`, `clinic_remote__book_appointment`, `git__git_commit`, so the model can always tell which server a tool belongs to. [`src/chatbot/mcp_client.py`](src/chatbot/mcp_client.py) handles the stdio transport, [`src/chatbot/mcp_http_client.py`](src/chatbot/mcp_http_client.py) handles the HTTP transport used for the remote server, both expose the same `start`, `call_tool` and `close` methods, so `app.py` treats every server the same way.

## Requirements

- Python 3.13 or newer, and [uv](https://docs.astral.sh/uv/)
- [Node.js](https://nodejs.org/), for the official Filesystem MCP server
- `uv` and `uvx`, also used to run the official Git MCP server, which is a Python package
- An Anthropic API key, see below

If your machine intercepts TLS traffic, for example a school network or an antivirus, and `uv` or `uvx` fail with an invalid peer certificate error, this project already sets `system-certs = true` in `pyproject.toml` and passes `--native-tls` to `uvx` for the git server, so it uses the certificate store of your operating system instead of its own bundled one.

## Setup

```bash
cd chatbot
uv sync
cp .env.example .env
# edit .env and set ANTHROPIC_API_KEY
```

You can get an API key from the [Anthropic Console](https://console.anthropic.com/), new accounts get 5 dollars of free credit, no card needed, and that is enough for this project.

## Running

```bash
uv run main.py
```

When it starts, you will see each MCP server connect, or fail to connect if a runtime is missing, the chatbot keeps working with whichever servers it could start, and then it shows the full list of tools available, after that it drops into a normal chat prompt:

```
You: create a repo in the workspace, add a README that says "hello", and commit it
Assistant: ...
You: what specialties does the clinic have?
Assistant: ...
You: exit
```

Every JSON-RPC message sent to or received from the MCP servers gets printed as it happens, and also saved under `logs/`, this covers the requirement of keeping and showing a log of all MCP interactions.

## Web UI, the extra credit interface

This project also includes an optional web interface, it is the same chatbot, same MCP wiring, same tools, just reached through a browser instead of the terminal. The static page lives in [`../frontend/`](../frontend/), it is plain HTML, CSS and JavaScript, no framework and no build step. The backend is [`src/chatbot/webserver.py`](src/chatbot/webserver.py), built with FastAPI, it reuses the same `ChatSession` class that the console version uses, so both share the same connection to the MCP servers, the same logging, and the same tool routing, only the transport around a chat turn changes, one HTTP request per message instead of a line typed in the terminal.

To run it:

```bash
cd chatbot
uv run web.py
```

Then open `http://127.0.0.1:8000/` in a browser. The page shows the connected servers and the available tools on the left, and a normal chat on the right, every time the model calls a tool, a small card appears in the chat showing which tool ran, what it received, and what it returned, so the log of MCP interactions stays visible without opening a terminal. The colors were chosen to feel calm and trustworthy for a clinic assistant, teal for the main chat, a soft amber only for tool activity, and red only for a real error, so the interface stays easy to read and does not feel alarming during normal use.

## Known limitation, git repo creation

The official `mcp-server-git`, published by Anthropic under `modelcontextprotocol/servers`, does not have a `git_init` tool, and it refuses to start if the `--repository` folder is not already a valid repo. Since there is no way to create a fresh repo through its own tools, the chatbot host runs `git init` once on `chatbot/workspace/` at startup, only if it is not a repo yet, see `src/chatbot/config.py::_ensure_git_repo`, this is just setup done by the host, not a tool call from the LLM. From that point on, creating the README with `filesystem__write_file`, staging it with `git__git_add`, and committing it with `git__git_commit`, all happens through normal conversation, exactly like the example in the assignment.

## Using the remote clinic server

The remote server is off by default, otherwise its tools would duplicate the local `clinic` server. To turn it on:

```bash
# .env
CHATBOT_ENABLE_CLINIC_REMOTE=1
CHATBOT_ENABLE_CLINIC=0
```

Turning off `CHATBOT_ENABLE_CLINIC` is optional, it just avoids having two copies of the same tools while comparing. See [`mcp_server_remote/README.md`](../mcp_server_remote/README.md) for how it was deployed and its known limitations, such as the state resetting on a cold start, and the two workarounds needed on the client side to reach Cloudflare reliably from this network, a browser style User-Agent and trusting the certificates from the operating system through the `truststore` package.

## Configuration

All configuration is done with environment variables, see `.env.example`:

| Variable | Purpose |
|---|---|
| `ANTHROPIC_API_KEY` | required, your Anthropic API key |
| `ANTHROPIC_MODEL` | defaults to `claude-sonnet-5` |
| `CHATBOT_ENABLE_CLINIC` / `_FILESYSTEM` / `_GIT` | set to `0` to turn off a local stdio server |
| `CHATBOT_ENABLE_CLINIC_REMOTE` | set to `1` to turn on the remote clinic server on Cloudflare |
| `CLINIC_REMOTE_URL` | address of the deployed Worker, defaults to the one in `mcp_server_remote/README.md` |
| `MCP_WORKSPACE_DIR` | sandbox folder for the filesystem and git servers, defaults to `chatbot/workspace/` |

## Project layout

```
chatbot/
├── main.py                     <- console entry point, run with `uv run main.py`
├── web.py                      <- web UI entry point, run with `uv run web.py`
├── src/chatbot/
│   ├── app.py                  <- ChatSession, chat loop, tool routing, conversation state
│   ├── webserver.py            <- FastAPI backend for the web UI, reuses ChatSession
│   ├── llm.py                  <- Anthropic Messages API wrapper
│   ├── mcp_client.py           <- JSON-RPC 2.0 client over stdio, written by hand
│   ├── mcp_http_client.py      <- JSON-RPC 2.0 client over HTTP, written by hand, for the remote server
│   ├── config.py               <- list of MCP servers to connect to
│   └── logging_util.py         <- logs every MCP request and response
├── logs/                        <- created while running, not tracked in git
└── workspace/                   <- sandbox for filesystem and git servers, not tracked in git

frontend/                        <- static web UI, plain HTML, CSS and JavaScript
├── index.html
├── style.css
└── app.js
```
