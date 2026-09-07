# Proyecto 1, Uso de un Protocolo Existente

CC3067 Redes, Universidad del Valle de Guatemala.
Student: Hugo Ernesto Barillas Villagran, Carnet 23306

This repository holds the deliverables for Project 1, which explores the Model Context Protocol, known as MCP, a chatbot host that connects to MCP servers, and a custom MCP server written by hand with JSON-RPC.

## Repository structure

```
Proyecto-1-redes/
├── README.md                <- you are here
├── Proyecto1.pdf             <- written report, server specs, Wireshark analysis, conclusions
├── mcp_server_v1/            <- Clinic Appointment MCP Server, local, manual JSON-RPC
│   ├── README.md               <- full server documentation, tools, setup, usage
│   ├── main.py                 <- server implementation
│   ├── pyproject.toml
│   └── src/
├── mcp_server_remote/        <- same server, deployed on Cloudflare Workers, HTTP transport
│   ├── README.md               <- deployment, endpoint, known limitations
│   └── src/index.js
├── chatbot/                  <- Chatbot host, Anthropic API plus MCP client
│   ├── README.md               <- setup, usage, architecture
│   ├── main.py                 <- console entry point
│   ├── web.py                  <- web UI entry point
│   ├── pyproject.toml
│   └── src/
└── frontend/                 <- static web UI, plain HTML, CSS and JavaScript
    ├── index.html
    ├── style.css
    └── app.js
```

## MCP Server

The custom MCP server, the Clinic Appointment MCP Server, lives in [`mcp_server_v1/`](mcp_server_v1/). See [`mcp_server_v1/README.md`](mcp_server_v1/README.md) for the full specification, the available tools, how to install it, and usage examples, including how to connect it to Claude Desktop.

The same server is also deployed remotely on Cloudflare Workers in [`mcp_server_remote/`](mcp_server_remote/), see its README for the live endpoint and the deployment steps.

## Chatbot Host

The chatbot host lives in [`chatbot/`](chatbot/). It talks to the Anthropic API directly, keeps conversation context, logs every MCP interaction, and connects to MCP servers over both stdio, for the custom Clinic Appointment server and the official Filesystem and Git servers, and HTTP, for the remote Cloudflare deployment of the clinic server. See [`chatbot/README.md`](chatbot/README.md) for setup and usage.

## Web UI

This is the extra credit User Interface. The same chatbot host can also be reached through a browser instead of the terminal, the static page lives in [`frontend/`](frontend/), plain HTML, CSS and JavaScript with no framework, and the backend is a small FastAPI server in `chatbot/src/chatbot/webserver.py` that reuses the exact same chat logic as the console version. Run it with `uv run web.py` from inside `chatbot/`, then open `http://127.0.0.1:8000/`. See the Web UI section in [`chatbot/README.md`](chatbot/README.md) for details.

## Report

[`Proyecto1.pdf`](Proyecto1.pdf) has the written report for this project, the specification of every server, the Wireshark analysis of the JSON-RPC traffic between the chatbot and the remote server, the difficulties found along the way, and the conclusions.
