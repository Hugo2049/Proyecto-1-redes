"""Clinic Appointment MCP Server.

Manual implementation of the Model Context Protocol (JSON-RPC 2.0 over
stdio), without using any MCP SDK.
"""

import sys
import json
from datetime import date, datetime, timedelta

SERVER_NAME = "clinic-appointment-mcp-server"
SERVER_VERSION = "0.1.0"
PROTOCOL_VERSION = "2025-11-25"

DATE_FORMAT = "%Y-%m-%d"
DATETIME_FORMAT = "%Y-%m-%d %H:%M"

class ToolError(Exception):
    """Raised when a tool receives invalid input or an invalid operation is requested."""


# ---------------------------------------------------------------------------
# In-memory data ("database")
# ---------------------------------------------------------------------------

SPECIALTIES = ["cardiologia", "dermatologia", "pediatria", "medicina_general"]

DOCTORS = [
    {"id": "doc-001", "name": "Dra. Ana Lopez", "specialty": "cardiologia"},
    {"id": "doc-002", "name": "Dr. Carlos Ruiz", "specialty": "cardiologia"},
    {"id": "doc-003", "name": "Dra. Maria Perez", "specialty": "dermatologia"},
    {"id": "doc-004", "name": "Dr. Jorge Gomez", "specialty": "pediatria"},
    {"id": "doc-005", "name": "Dra. Laura Diaz", "specialty": "medicina_general"},
]

DEFAULT_SLOTS = ["08:00", "09:00", "10:00", "11:00", "14:00", "15:00", "16:00"]

# doctor_id -> {date_str: [available time strings]}
availability: dict[str, dict[str, list[str]]] = {}

# appointment_id -> appointment record
appointments: dict[str, dict] = {}
_appointment_counter = 0


def _find_doctor(doctor_id: str) -> dict:
    for doctor in DOCTORS:
        if doctor["id"] == doctor_id:
            return doctor
    raise ToolError(f"No existe un medico con id '{doctor_id}'")


def _slots_for(doctor_id: str, date_str: str) -> list[str]:
    day_slots = availability.setdefault(doctor_id, {})
    return day_slots.setdefault(date_str, list(DEFAULT_SLOTS))


def _parse_date(value: str, field: str) -> date:
    try:
        return datetime.strptime(value, DATE_FORMAT).date()
    except (TypeError, ValueError):
        raise ToolError(f"'{field}' debe tener el formato YYYY-MM-DD")


def _parse_datetime(value: str, field: str) -> datetime:
    try:
        return datetime.strptime(value, DATETIME_FORMAT)
    except (TypeError, ValueError):
        raise ToolError(f"'{field}' debe tener el formato YYYY-MM-DD HH:MM")


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------

def list_specialties(_args: dict) -> dict:
    return {"specialties": SPECIALTIES}


def list_doctors(args: dict) -> dict:
    specialty = args.get("specialty")
    if not specialty:
        raise ToolError("El parametro 'specialty' es requerido")

    matches = [d for d in DOCTORS if d["specialty"].lower() == specialty.lower()]
    return {"doctors": matches}


def check_availability(args: dict) -> dict:
    doctor_id = args.get("doctor_id")
    date_from = args.get("date_from")
    date_to = args.get("date_to")
    if not doctor_id or not date_from or not date_to:
        raise ToolError("'doctor_id', 'date_from' y 'date_to' son requeridos")

    _find_doctor(doctor_id)
    start = _parse_date(date_from, "date_from")
    end = _parse_date(date_to, "date_to")
    if end < start:
        raise ToolError("'date_to' debe ser igual o posterior a 'date_from'")

    schedule = {}
    current = start
    while current <= end:
        date_str = current.isoformat()
        schedule[date_str] = list(_slots_for(doctor_id, date_str))
        current += timedelta(days=1)

    return {"doctor_id": doctor_id, "availability": schedule}


def book_appointment(args: dict) -> dict:
    global _appointment_counter

    doctor_id = args.get("doctor_id")
    patient_name = args.get("patient_name")
    appointment_datetime = args.get("datetime")
    if not doctor_id or not patient_name or not appointment_datetime:
        raise ToolError("'doctor_id', 'patient_name' y 'datetime' son requeridos")

    _find_doctor(doctor_id)
    parsed = _parse_datetime(appointment_datetime, "datetime")
    date_str, time_str = parsed.date().isoformat(), parsed.strftime("%H:%M")

    slots = _slots_for(doctor_id, date_str)
    if time_str not in slots:
        raise ToolError(f"El horario {time_str} del {date_str} no esta disponible")

    slots.remove(time_str)
    _appointment_counter += 1
    appointment_id = f"apt-{_appointment_counter:04d}"
    appointments[appointment_id] = {
        "id": appointment_id,
        "doctor_id": doctor_id,
        "patient_name": patient_name,
        "datetime": f"{date_str} {time_str}",
        "status": "confirmed",
    }
    return dict(appointments[appointment_id])


def cancel_appointment(args: dict) -> dict:
    appointment_id = args.get("appointment_id")
    if not appointment_id:
        raise ToolError("El parametro 'appointment_id' es requerido")

    appointment = appointments.get(appointment_id)
    if appointment is None:
        raise ToolError(f"No existe una cita con id '{appointment_id}'")
    if appointment["status"] == "cancelled":
        raise ToolError(f"La cita '{appointment_id}' ya se encuentra cancelada")

    appointment["status"] = "cancelled"
    date_str, time_str = appointment["datetime"].split(" ")
    _slots_for(appointment["doctor_id"], date_str).append(time_str)
    return dict(appointment)


def reschedule_appointment(args: dict) -> dict:
    appointment_id = args.get("appointment_id")
    new_datetime = args.get("new_datetime")
    if not appointment_id or not new_datetime:
        raise ToolError("'appointment_id' y 'new_datetime' son requeridos")

    appointment = appointments.get(appointment_id)
    if appointment is None:
        raise ToolError(f"No existe una cita con id '{appointment_id}'")
    if appointment["status"] != "confirmed":
        raise ToolError(f"La cita '{appointment_id}' no se puede reprogramar")

    parsed = _parse_datetime(new_datetime, "new_datetime")
    new_date_str, new_time_str = parsed.date().isoformat(), parsed.strftime("%H:%M")

    new_slots = _slots_for(appointment["doctor_id"], new_date_str)
    if new_time_str not in new_slots:
        raise ToolError(f"El horario {new_time_str} del {new_date_str} no esta disponible")

    old_date_str, old_time_str = appointment["datetime"].split(" ")
    _slots_for(appointment["doctor_id"], old_date_str).append(old_time_str)
    new_slots.remove(new_time_str)
    appointment["datetime"] = f"{new_date_str} {new_time_str}"
    return dict(appointment)


# ---------------------------------------------------------------------------
# Tool registry: MCP tool definitions + handlers
# ---------------------------------------------------------------------------

TOOLS = [
    {
        "name": "list_specialties",
        "description": "Devuelve la lista de especialidades medicas disponibles en la clinica.",
        "inputSchema": {"type": "object", "properties": {}, "required": []},
        "handler": list_specialties,
    },
    {
        "name": "list_doctors",
        "description": "Devuelve los medicos disponibles para una especialidad determinada.",
        "inputSchema": {
            "type": "object",
            "properties": {"specialty": {"type": "string"}},
            "required": ["specialty"],
        },
        "handler": list_doctors,
    },
    {
        "name": "check_availability",
        "description": "Devuelve los horarios disponibles de un medico en un rango de fechas.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "doctor_id": {"type": "string"},
                "date_from": {"type": "string", "description": "Formato YYYY-MM-DD"},
                "date_to": {"type": "string", "description": "Formato YYYY-MM-DD"},
            },
            "required": ["doctor_id", "date_from", "date_to"],
        },
        "handler": check_availability,
    },
    {
        "name": "book_appointment",
        "description": "Registra una cita nueva para un paciente con un medico en un horario especifico.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "doctor_id": {"type": "string"},
                "patient_name": {"type": "string"},
                "datetime": {"type": "string", "description": "Formato YYYY-MM-DD HH:MM"},
            },
            "required": ["doctor_id", "patient_name", "datetime"],
        },
        "handler": book_appointment,
    },
    {
        "name": "cancel_appointment",
        "description": "Cancela una cita previamente registrada.",
        "inputSchema": {
            "type": "object",
            "properties": {"appointment_id": {"type": "string"}},
            "required": ["appointment_id"],
        },
        "handler": cancel_appointment,
    },
    {
        "name": "reschedule_appointment",
        "description": "Modifica la fecha u hora de una cita existente.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "appointment_id": {"type": "string"},
                "new_datetime": {"type": "string", "description": "Formato YYYY-MM-DD HH:MM"},
            },
            "required": ["appointment_id", "new_datetime"],
        },
        "handler": reschedule_appointment,
    },
]

TOOL_HANDLERS = {tool["name"]: tool["handler"] for tool in TOOLS}


# ---------------------------------------------------------------------------
# JSON-RPC 2.0 transport (stdio)
# ---------------------------------------------------------------------------

def log(message: str) -> None:
    """Write diagnostics to stderr; stdout is reserved for JSON-RPC messages."""
    print(f"[{SERVER_NAME}] {message}", file=sys.stderr, flush=True)


def send_message(message: dict) -> None:
    sys.stdout.write(json.dumps(message) + "\n")
    sys.stdout.flush()


def send_result(request_id, result: dict) -> None:
    send_message({"jsonrpc": "2.0", "id": request_id, "result": result})


def send_error(request_id, code: int, message: str) -> None:
    send_message({"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}})


def handle_initialize(request_id, params: dict) -> None:
    send_result(request_id, {
        "protocolVersion": PROTOCOL_VERSION,
        "capabilities": {"tools": {}},
        "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
    })


def handle_tools_list(request_id, params: dict) -> None:
    tools = [{"name": t["name"], "description": t["description"], "inputSchema": t["inputSchema"]} for t in TOOLS]
    send_result(request_id, {"tools": tools})


def handle_tools_call(request_id, params: dict) -> None:
    name = params.get("name")
    arguments = params.get("arguments") or {}

    handler = TOOL_HANDLERS.get(name)
    if handler is None:
        send_error(request_id, -32602, f"Herramienta desconocida: '{name}'")
        return

    try:
        result = handler(arguments)
    except ToolError as exc:
        send_result(request_id, {"content": [{"type": "text", "text": str(exc)}], "isError": True})
        return

    send_result(request_id, {"content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False)}]})


REQUEST_HANDLERS = {
    "initialize": handle_initialize,
    "tools/list": handle_tools_list,
    "tools/call": handle_tools_call,
}


def dispatch(message: dict) -> None:
    method = message.get("method")
    request_id = message.get("id")
    params = message.get("params") or {}

    if method == "notifications/initialized":
        return  # client acknowledgment, no response expected

    handler = REQUEST_HANDLERS.get(method)
    if handler is None:
        if request_id is not None:
            send_error(request_id, -32601, f"Metodo no soportado: '{method}'")
        return

    handler(request_id, params)


def main() -> None:
    log(f"{SERVER_NAME} v{SERVER_VERSION} listo, esperando mensajes JSON-RPC por stdin...")
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue

        try:
            message = json.loads(line)
        except json.JSONDecodeError:
            send_error(None, -32700, "Parse error: JSON invalido")
            continue

        log(f"-> {line}")
        try:
            dispatch(message)
        except Exception as exc:  # noqa: BLE001 - guard the read loop against handler bugs
            send_error(message.get("id"), -32603, f"Error interno: {exc}")


if __name__ == "__main__":
    main()
