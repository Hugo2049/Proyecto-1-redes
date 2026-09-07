/**
 * Clinic Appointment MCP Server — remote deployment (Cloudflare Workers).
 *
 * Same tool set and JSON-RPC 2.0 semantics as the local server
 * (mcp_server_v1/main.py), but transported over HTTP instead of stdio, as
 * required by functionality #6 of the project statement. No MCP SDK is
 * used: the JSON-RPC message handling below is written by hand, mirroring
 * the local server's dispatch logic 1:1.
 */

const SERVER_NAME = "clinic-appointment-mcp-server-remote";
const SERVER_VERSION = "0.1.0";
const PROTOCOL_VERSION = "2025-11-25";

class ToolError extends Error {}

// ---------------------------------------------------------------------------
// In-memory data ("database"). Lives for as long as this Worker isolate is
// warm. Cloudflare may spin up a fresh isolate (e.g. after being idle, or to
// serve a request from a different edge location), which resets this state.
// That's an accepted limitation for this class project: a production
// deployment would back this with Workers KV or a Durable Object instead.
// ---------------------------------------------------------------------------

const SPECIALTIES = ["cardiologia", "dermatologia", "pediatria", "medicina_general"];

const DOCTORS = [
  { id: "doc-001", name: "Dra. Ana Lopez", specialty: "cardiologia" },
  { id: "doc-002", name: "Dr. Carlos Ruiz", specialty: "cardiologia" },
  { id: "doc-003", name: "Dra. Maria Perez", specialty: "dermatologia" },
  { id: "doc-004", name: "Dr. Jorge Gomez", specialty: "pediatria" },
  { id: "doc-005", name: "Dra. Laura Diaz", specialty: "medicina_general" },
];

const DEFAULT_SLOTS = ["08:00", "09:00", "10:00", "11:00", "14:00", "15:00", "16:00"];

const availability = {}; // doctor_id -> { date_str: [slot, ...] }
const appointments = {}; // appointment_id -> record
let appointmentCounter = 0;

function findDoctor(doctorId) {
  const doctor = DOCTORS.find((d) => d.id === doctorId);
  if (!doctor) throw new ToolError(`No existe un medico con id '${doctorId}'`);
  return doctor;
}

function slotsFor(doctorId, dateStr) {
  if (!availability[doctorId]) availability[doctorId] = {};
  if (!availability[doctorId][dateStr]) availability[doctorId][dateStr] = [...DEFAULT_SLOTS];
  return availability[doctorId][dateStr];
}

function assertDate(value, field) {
  if (typeof value !== "string" || !/^\d{4}-\d{2}-\d{2}$/.test(value) || Number.isNaN(Date.parse(value))) {
    throw new ToolError(`'${field}' debe tener el formato YYYY-MM-DD`);
  }
  return value;
}

function assertDatetime(value, field) {
  if (typeof value !== "string" || !/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$/.test(value)) {
    throw new ToolError(`'${field}' debe tener el formato YYYY-MM-DD HH:MM`);
  }
  const [dateStr, timeStr] = value.split(" ");
  if (Number.isNaN(Date.parse(dateStr))) throw new ToolError(`'${field}' debe tener el formato YYYY-MM-DD HH:MM`);
  return { dateStr, timeStr };
}

function addDays(dateStr, days) {
  const d = new Date(`${dateStr}T00:00:00Z`);
  d.setUTCDate(d.getUTCDate() + days);
  return d.toISOString().slice(0, 10);
}

// ---------------------------------------------------------------------------
// Tool implementations
// ---------------------------------------------------------------------------

function listSpecialties() {
  return { specialties: SPECIALTIES };
}

function listDoctors(args) {
  const specialty = args.specialty;
  if (!specialty) throw new ToolError("El parametro 'specialty' es requerido");
  const matches = DOCTORS.filter((d) => d.specialty.toLowerCase() === String(specialty).toLowerCase());
  return { doctors: matches };
}

function checkAvailability(args) {
  const { doctor_id: doctorId, date_from: dateFrom, date_to: dateTo } = args;
  if (!doctorId || !dateFrom || !dateTo) throw new ToolError("'doctor_id', 'date_from' y 'date_to' son requeridos");
  findDoctor(doctorId);
  assertDate(dateFrom, "date_from");
  assertDate(dateTo, "date_to");
  if (dateTo < dateFrom) throw new ToolError("'date_to' debe ser igual o posterior a 'date_from'");

  const schedule = {};
  let current = dateFrom;
  while (current <= dateTo) {
    schedule[current] = [...slotsFor(doctorId, current)];
    current = addDays(current, 1);
  }
  return { doctor_id: doctorId, availability: schedule };
}

function bookAppointment(args) {
  const { doctor_id: doctorId, patient_name: patientName, datetime } = args;
  if (!doctorId || !patientName || !datetime) throw new ToolError("'doctor_id', 'patient_name' y 'datetime' son requeridos");
  findDoctor(doctorId);
  const { dateStr, timeStr } = assertDatetime(datetime, "datetime");

  const slots = slotsFor(doctorId, dateStr);
  const idx = slots.indexOf(timeStr);
  if (idx === -1) throw new ToolError(`El horario ${timeStr} del ${dateStr} no esta disponible`);
  slots.splice(idx, 1);

  appointmentCounter += 1;
  const appointmentId = `apt-${String(appointmentCounter).padStart(4, "0")}`;
  appointments[appointmentId] = {
    id: appointmentId,
    doctor_id: doctorId,
    patient_name: patientName,
    datetime: `${dateStr} ${timeStr}`,
    status: "confirmed",
  };
  return { ...appointments[appointmentId] };
}

function cancelAppointment(args) {
  const appointmentId = args.appointment_id;
  if (!appointmentId) throw new ToolError("El parametro 'appointment_id' es requerido");
  const appointment = appointments[appointmentId];
  if (!appointment) throw new ToolError(`No existe una cita con id '${appointmentId}'`);
  if (appointment.status === "cancelled") throw new ToolError(`La cita '${appointmentId}' ya se encuentra cancelada`);

  appointment.status = "cancelled";
  const [dateStr, timeStr] = appointment.datetime.split(" ");
  slotsFor(appointment.doctor_id, dateStr).push(timeStr);
  return { ...appointment };
}

function rescheduleAppointment(args) {
  const { appointment_id: appointmentId, new_datetime: newDatetime } = args;
  if (!appointmentId || !newDatetime) throw new ToolError("'appointment_id' y 'new_datetime' son requeridos");
  const appointment = appointments[appointmentId];
  if (!appointment) throw new ToolError(`No existe una cita con id '${appointmentId}'`);
  if (appointment.status !== "confirmed") throw new ToolError(`La cita '${appointmentId}' no se puede reprogramar`);

  const { dateStr: newDateStr, timeStr: newTimeStr } = assertDatetime(newDatetime, "new_datetime");
  const newSlots = slotsFor(appointment.doctor_id, newDateStr);
  if (!newSlots.includes(newTimeStr)) throw new ToolError(`El horario ${newTimeStr} del ${newDateStr} no esta disponible`);

  const [oldDateStr, oldTimeStr] = appointment.datetime.split(" ");
  slotsFor(appointment.doctor_id, oldDateStr).push(oldTimeStr);
  newSlots.splice(newSlots.indexOf(newTimeStr), 1);
  appointment.datetime = `${newDateStr} ${newTimeStr}`;
  return { ...appointment };
}

// ---------------------------------------------------------------------------
// Tool registry: MCP tool definitions + handlers (mirrors mcp_server_v1/main.py)
// ---------------------------------------------------------------------------

const TOOLS = [
  {
    name: "list_specialties",
    description: "Devuelve la lista de especialidades medicas disponibles en la clinica.",
    inputSchema: { type: "object", properties: {}, required: [] },
    handler: listSpecialties,
  },
  {
    name: "list_doctors",
    description: "Devuelve los medicos disponibles para una especialidad determinada.",
    inputSchema: {
      type: "object",
      properties: { specialty: { type: "string" } },
      required: ["specialty"],
    },
    handler: listDoctors,
  },
  {
    name: "check_availability",
    description: "Devuelve los horarios disponibles de un medico en un rango de fechas.",
    inputSchema: {
      type: "object",
      properties: {
        doctor_id: { type: "string" },
        date_from: { type: "string", description: "Formato YYYY-MM-DD" },
        date_to: { type: "string", description: "Formato YYYY-MM-DD" },
      },
      required: ["doctor_id", "date_from", "date_to"],
    },
    handler: checkAvailability,
  },
  {
    name: "book_appointment",
    description: "Registra una cita nueva para un paciente con un medico en un horario especifico.",
    inputSchema: {
      type: "object",
      properties: {
        doctor_id: { type: "string" },
        patient_name: { type: "string" },
        datetime: { type: "string", description: "Formato YYYY-MM-DD HH:MM" },
      },
      required: ["doctor_id", "patient_name", "datetime"],
    },
    handler: bookAppointment,
  },
  {
    name: "cancel_appointment",
    description: "Cancela una cita previamente registrada.",
    inputSchema: {
      type: "object",
      properties: { appointment_id: { type: "string" } },
      required: ["appointment_id"],
    },
    handler: cancelAppointment,
  },
  {
    name: "reschedule_appointment",
    description: "Modifica la fecha u hora de una cita existente.",
    inputSchema: {
      type: "object",
      properties: {
        appointment_id: { type: "string" },
        new_datetime: { type: "string", description: "Formato YYYY-MM-DD HH:MM" },
      },
      required: ["appointment_id", "new_datetime"],
    },
    handler: rescheduleAppointment,
  },
];

const TOOL_HANDLERS = Object.fromEntries(TOOLS.map((t) => [t.name, t.handler]));

// ---------------------------------------------------------------------------
// JSON-RPC 2.0 dispatch (transported over HTTP instead of stdio)
// ---------------------------------------------------------------------------

function handleInitialize() {
  return {
    protocolVersion: PROTOCOL_VERSION,
    capabilities: { tools: {} },
    serverInfo: { name: SERVER_NAME, version: SERVER_VERSION },
  };
}

function handleToolsList() {
  return { tools: TOOLS.map(({ name, description, inputSchema }) => ({ name, description, inputSchema })) };
}

function handleToolsCall(params) {
  const name = params?.name;
  const args = params?.arguments || {};
  const handler = TOOL_HANDLERS[name];
  if (!handler) {
    return { __error: { code: -32602, message: `Herramienta desconocida: '${name}'` } };
  }
  try {
    const result = handler(args);
    return { content: [{ type: "text", text: JSON.stringify(result) }] };
  } catch (err) {
    if (err instanceof ToolError) {
      return { content: [{ type: "text", text: err.message }], isError: true };
    }
    throw err;
  }
}

const REQUEST_HANDLERS = {
  initialize: () => handleInitialize(),
  "tools/list": () => handleToolsList(),
  "tools/call": (params) => handleToolsCall(params),
};

function dispatch(message) {
  const { method, id, params } = message;

  if (method === "notifications/initialized") {
    return null; // acknowledgement, no response
  }

  const handler = REQUEST_HANDLERS[method];
  if (!handler) {
    if (id === undefined || id === null) return null;
    return { jsonrpc: "2.0", id, error: { code: -32601, message: `Metodo no soportado: '${method}'` } };
  }

  try {
    const result = handler(params || {});
    if (result && result.__error) {
      return { jsonrpc: "2.0", id, error: result.__error };
    }
    return { jsonrpc: "2.0", id, result };
  } catch (err) {
    return { jsonrpc: "2.0", id, error: { code: -32603, message: `Error interno: ${err.message}` } };
  }
}

export default {
  async fetch(request) {
    if (request.method === "GET") {
      return new Response(`${SERVER_NAME} v${SERVER_VERSION} — POST JSON-RPC 2.0 messages here.\n`, { status: 200 });
    }
    if (request.method !== "POST") {
      return new Response("Method not allowed", { status: 405 });
    }

    let message;
    try {
      message = await request.json();
    } catch {
      return new Response(JSON.stringify({ jsonrpc: "2.0", id: null, error: { code: -32700, message: "Parse error: JSON invalido" } }), {
        status: 400,
        headers: { "content-type": "application/json" },
      });
    }

    const response = dispatch(message);
    if (response === null) {
      return new Response(null, { status: 202 });
    }
    return new Response(JSON.stringify(response), { headers: { "content-type": "application/json" } });
  },
};
