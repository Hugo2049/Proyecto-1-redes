# Clinic Appointment MCP Server

This is a local MCP server, MCP stands for Model Context Protocol, it lets a chatbot talk to a patient, understand what they need, and manage medical appointments for them, checking specialties, listing doctors, checking availability, booking, rescheduling and cancelling appointments.

The server is written by hand with JSON-RPC 2.0 over stdio, using only the Python standard library, `json`, `sys` and `datetime`. No MCP SDK, such as `mcp[cli]` or FastMCP, is used, since the assignment asks for that.

## Tools

| Tool | Description | Parameters |
|---|---|---|
| `list_specialties` | Returns the medical specialties the clinic offers | none |
| `list_doctors` | Returns the doctors for a given specialty | `specialty` string |
| `check_availability` | Returns a doctor's open time slots in a date range | `doctor_id` string, `date_from` string in `YYYY-MM-DD`, `date_to` string in `YYYY-MM-DD` |
| `book_appointment` | Books a new appointment for a patient | `doctor_id` string, `patient_name` string, `datetime` string in `YYYY-MM-DD HH:MM` |
| `cancel_appointment` | Cancels an existing appointment | `appointment_id` string |
| `reschedule_appointment` | Changes the date and time of an existing appointment | `appointment_id` string, `new_datetime` string in `YYYY-MM-DD HH:MM` |

The data, specialties, doctors, availability and appointments, all live in memory, and get filled with sample data every time the server starts.

## Requirements

- Python 3.13 or newer
- [uv](https://docs.astral.sh/uv/)

## Installation

```bash
git clone <this-repository-url>
cd mcp_server_v1
uv sync
```

## Running the server on its own

```bash
uv run main.py
```

The server prints a ready message to `stderr`, and then waits for JSON-RPC messages on `stdin`, one JSON object per line, responses go to `stdout` in the same way. This is normal for an MCP server that uses stdio, the process is not supposed to exit on its own.

## Using it with Claude Desktop

1. Open, or create, the Claude Desktop config file:
   - `%APPDATA%\Claude\claude_desktop_config.json`, or
   - if you installed the Microsoft Store version of Claude Desktop, `%LOCALAPPDATA%\Packages\Claude_<id>\LocalCache\Roaming\Claude\claude_desktop_config.json`
2. Add an entry under `mcpServers`:

```json
{
  "mcpServers": {
    "clinic-appointment": {
      "command": "uv",
      "args": [
        "run",
        "--directory",
        "ABSOLUTE_PATH_TO/mcp_server_v1",
        "main.py"
      ]
    }
  }
}
```

3. Quit Claude Desktop completely, from the system tray, not just closing the window, then open it again.
4. In the Connectors panel, `clinic-appointment` should show up as connected, with the 6 tools listed above.

## Example interaction

Patient: I need an appointment with a cardiologist as soon as possible.

1. The chatbot calls `list_specialties` and sees that cardiology is offered.
2. It calls `list_doctors` with `specialty` set to `cardiologia`, to get the list of cardiologists.
3. Once the patient picks a doctor, it calls `check_availability` with that doctor's id and a nearby date range, and shows the open time slots.
4. Once the patient confirms a slot, it calls `book_appointment` with the patient data and the chosen slot, and shows the confirmation, the appointment id.

## Notes on how this was built

The project started with `uv`, and the first connection test against Claude Desktop followed [this video](https://www.youtube.com/watch?v=-8k9lGpGQ6g&t=181s). That tutorial builds the server on top of the official `mcp` SDK, which hides the JSON-RPC protocol, that is not allowed for this assignment, since the goal is to write the message exchange by hand. Once that first setup worked, Claude Code was used to rewrite `main.py` from the ground up as a plain JSON-RPC 2.0 handler, `initialize`, `tools/list`, `tools/call`, with no MCP SDK, and to add the sample data, specialties, doctors, availability, and the six tools from the project proposal.

The hardest part, though not too hard, was getting Claude Desktop to actually see the server, it did not show up in the Connectors list on the first few tries. It turned out the packaged version of Claude Desktop reads its config from a different path than the usual `%APPDATA%\Claude` one. Once the config file was placed in the right spot, the server connected and its tools showed up.


<img width="1355" height="1152" alt="image" src="https://github.com/user-attachments/assets/9ce130a0-bf03-47d6-bfb1-f089961c84fc" />


<img width="1372" height="1133" alt="image" src="https://github.com/user-attachments/assets/b7f276ea-02a0-45c8-bbe0-ff488efe0da4" />

