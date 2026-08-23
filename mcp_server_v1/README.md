# Clinic Appointment MCP Server

A local MCP (Model Context Protocol) server that lets a chatbot talk to a patient, understand what they need, and manage medical appointments on their behalf: checking specialties, listing doctors, checking availability, booking, rescheduling, and cancelling appointments.

The server is implemented **manually with JSON-RPC 2.0 over stdio**, using only Python's standard library (`json`, `sys`, `datetime`). No MCP SDK (such as `mcp[cli]` / FastMCP) is used, as required by the project statement.

## Tools

| Tool | Description | Parameters |
|---|---|---|
| `list_specialties` | Returns the medical specialties available at the clinic | none |
| `list_doctors` | Returns the doctors available for a given specialty | `specialty` (string) |
| `check_availability` | Returns a doctor's available time slots in a date range | `doctor_id` (string), `date_from` (string, `YYYY-MM-DD`), `date_to` (string, `YYYY-MM-DD`) |
| `book_appointment` | Books a new appointment for a patient | `doctor_id` (string), `patient_name` (string), `datetime` (string, `YYYY-MM-DD HH:MM`) |
| `cancel_appointment` | Cancels an existing appointment | `appointment_id` (string) |
| `reschedule_appointment` | Changes the date/time of an existing appointment | `appointment_id` (string), `new_datetime` (string, `YYYY-MM-DD HH:MM`) |

Data (specialties, doctors, availability, appointments) is stored in memory and seeded with sample data when the server starts.

## Requirements

- Python 3.13+
- [uv](https://docs.astral.sh/uv/)

## Installation

```bash
git clone <this-repository-url>
cd mcp_server_v1
uv sync
```

## Running the server standalone

```bash
uv run main.py
```

The server will print a ready message to `stderr` and then wait for JSON-RPC messages on `stdin`, one JSON object per line. Responses are written to `stdout` in the same format. This is normal MCP stdio behavior — the process does not exit by itself.

## Using it with Claude Desktop

1. Open (or create) Claude Desktop's config file:
   - `%APPDATA%\Claude\claude_desktop_config.json`, or
   - if using the Microsoft Store / packaged version of Claude Desktop: `%LOCALAPPDATA%\Packages\Claude_<id>\LocalCache\Roaming\Claude\claude_desktop_config.json`
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

3. Fully quit Claude Desktop (from the system tray, not just close the window) and reopen it.
4. In the "Connectors" / tools panel, `clinic-appointment` should appear as connected, exposing the 6 tools above.

## Example interaction

> **Patient:** I need an appointment with a cardiologist as soon as possible.

1. The chatbot calls `list_specialties` and confirms cardiology is available.
2. It calls `list_doctors` with `specialty = "cardiologia"` to get the list of cardiologists.
3. Once the patient picks a doctor, it calls `check_availability` with the doctor's id and a nearby date range, and shows the open time slots.
4. After the patient confirms a slot, it calls `book_appointment` with the patient's data and the chosen slot, and returns the confirmation (`appointment_id`).

## Notes on the development process

The project was scaffolded with `uv` and the first connectivity test against Claude Desktop was done following [this video](https://www.youtube.com/watch?v=-8k9lGpGQ6g&t=181s). That tutorial builds the server on top of the official `mcp` SDK, which abstracts away the JSON-RPC protocol — not allowed for this assignment, since the goal is to implement the message exchange manually. After confirming the basic setup worked, Claude Code was used to rewrite `main.py` from scratch as a plain JSON-RPC 2.0 handler (`initialize`, `tools/list`, `tools/call`) with no MCP SDK dependency, and to seed it with the sample data (specialties, doctors, availability) and the six tools defined in the project proposal.

The trickiest part (though not too difficult) was getting Claude Desktop to actually detect the server: it didn't show up in the Connectors list during the first attempts. It turned out the packaged version of Claude Desktop reads its config from a different path than the classic `%APPDATA%\Claude` location. Once the config file was updated in the right place, the server connected and its tools became available.
