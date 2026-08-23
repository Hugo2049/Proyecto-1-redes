# Proyecto 1 - Uso de un Protocolo Existente

CC3067 Redes, Universidad del Valle de Guatemala.
Student: Hugo Ernesto Barillas Villagran - Carnet 23306

This repository contains the deliverables for Project 1, which explores the **Model Context Protocol (MCP)**: a chatbot host that connects to MCP servers, and a custom local MCP server implemented manually with JSON-RPC.

## Repository structure

```
Proyecto-1-redes/
├── README.md               <- you are here
├── pruebas/                 <- assignment statement and proposal reference docs
└── mcp_server_v1/           <- Clinic Appointment MCP Server (local, manual JSON-RPC)
    ├── README.md             <- full server documentation: tools, setup, usage
    ├── main.py               <- server implementation
    ├── pyproject.toml
    └── src/
```

## MCP Server

The custom local MCP server (**Clinic Appointment MCP Server**) lives in [`mcp_server_v1/`](mcp_server_v1/). See [`mcp_server_v1/README.md`](mcp_server_v1/README.md) for the full specification: available tools, installation, and usage examples (including how to connect it to Claude Desktop).

Other project deliverables (chatbot host, official Filesystem/Git MCP integration, remote deployment, Wireshark analysis) will be added to this repository as they are completed.
