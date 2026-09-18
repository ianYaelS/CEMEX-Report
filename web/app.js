import {
  expectedStorageKey,
  functionPageUrl,
  functionStorageUrl,
  connectSamsara,
  listFunctions,
  listVehicles,
  startFunctionRun,
  waitForFunctionRun,
} from "./samsara.js";

const $ = (id) => document.getElementById(id);

const state = {
  vehicles: [],
  functions: [],
  unlocked: false,
  apiRoot: "",
  config: {
    functionName: "cemex-telemetry-report-ui",
    functionNames: ["cemex-telemetry-report-ui"],
    orgId: "11006658",
    apiBaseUrl: "https://api.samsara.com",
    proxyUrl: "",
    storagePrefix: "CEMEX_Reportes",
    storageUrl:
      "https://cloud.samsara.com/o/11006658/fleet/config/functions?view=storage&name=cemex-telemetry-report-ui",
    functionUrl: "https://cloud.samsara.com/o/11006658/fleet/config/functions?name=cemex-telemetry-report-ui",
    maxRangeDays: 7,
  },
};

function setStatus(id, text, kind) {
  const node = $(id);
  if (!node) return;
  node.textContent = text;
  node.className = `status ${kind || ""}`;
}

function token() {
  return $("token").value.trim();
}

function apiRoot() {
  return state.apiRoot;
}

function selectedFunctionName() {
  return $("function").value.trim();
}

function selectedFunction() {
  return state.functions.find((item) => item.name === selectedFunctionName());
}

function daySpan(start, end) {
  const a = new Date(`${start}T00:00:00`);
  const b = new Date(`${end}T00:00:00`);
  return Math.round((b - a) / 86400000) + 1;
}

function renderVehicles(query) {
  const needle = (query || "").trim().toLowerCase();
  const select = $("vehicle");
  const current = select.value;
  const matches = state.vehicles.filter((item) => {
    if (!needle) return true;
    return `${item.label} ${item.id} ${item.name} ${item.licensePlate}`.toLowerCase().includes(needle);
  });
  select.innerHTML = "";
  if (!matches.length) {
    const empty = document.createElement("option");
    empty.value = "";
    empty.textContent = "Sin unidades para ese filtro";
    select.append(empty);
    return;
  }
  for (const item of matches) {
    const option = document.createElement("option");
    option.value = item.id;
    option.textContent = item.label;
    select.append(option);
  }
  if (matches.some((item) => item.id === current)) select.value = current;
}

function renderFunctions() {
  const select = $("function");
  const preferred = state.config.functionName;
  select.innerHTML = "";
  if (!state.functions.length) {
    const empty = document.createElement("option");
    empty.value = "";
    empty.textContent = "No se encontró ninguna Function con este token";
    select.append(empty);
    return;
  }
  for (const item of state.functions) {
    const option = document.createElement("option");
    option.value = item.name;
    option.textContent = item.description ? `${item.name} — ${item.description}` : item.name;
    select.append(option);
  }
  if (state.functions.some((item) => item.name === preferred)) select.value = preferred;
  updateFunctionLinks();
}

function updateFunctionLinks() {
  const name = selectedFunctionName() || state.config.functionName;
  $("storageLink").href = functionStorageUrl(state.config.orgId, name);
  $("functionLink").href = functionPageUrl(state.config.orgId, name);
  $("generate").textContent = name ? `Generar con ${name}` : "Generar reporte";
}

function lockWorkspace() {
  state.unlocked = false;
  state.apiRoot = "";
  state.vehicles = [];
  state.functions = [];
  $("token").value = "";
  $("workspace").classList.add("hidden");
  $("gate").classList.remove("hidden");
  $("result").classList.add("hidden");
  setStatus("gateStatus", "Sesión cerrada. El token no quedó guardado.", "");
  $("token").focus();
}

function unlockWorkspace() {
  state.unlocked = true;
  $("gate").classList.add("hidden");
  $("workspace").classList.remove("hidden");
  $("fleetMeta").textContent = `${state.vehicles.length} unidades · ${state.functions.length} Functions`;
  renderFunctions();
  renderVehicles("");
}

function showResult({ vehicle, start, end, correlationId, status, functionName }) {
  const keys = expectedStorageKey({
    prefix: state.config.storagePrefix,
    vehicleId: vehicle.id,
    vehicleName: vehicle.name,
    startDate: start,
    endDate: end,
  });
  $("result").classList.remove("hidden");
  $("resultSummary").textContent = `${functionName} · ${status || "success"} · ${vehicle.name}`;
  $("storagePath").textContent = `Archivo en Storage: ${keys.storageKey}`;
  $("correlation").textContent = `correlationId: ${correlationId} · Function: ${functionName}`;
  updateFunctionLinks();
}

async function loadConfig() {
  const response = await fetch("./config.json", { cache: "no-store" });
  if (response.ok) state.config = { ...state.config, ...(await response.json()) };
}

async function unlock() {
  if (!token()) {
    setStatus("gateStatus", "Pega el API token para desbloquear.", "err");
    $("token").focus();
    return;
  }
  $("unlock").disabled = true;
  setStatus("gateStatus", "Conectando con Samsara…");
  try {
    state.apiRoot = await connectSamsara(state.config, token());
    const [vehicles, functions] = await Promise.all([
      listVehicles(state.apiRoot, token()),
      listFunctions(state.apiRoot, token(), state.config.functionNames || [state.config.functionName]),
    ]);
    state.vehicles = vehicles;
    state.functions = functions;
    if (!state.vehicles.length) {
      throw new Error("El token funcionó pero la org no tiene unidades visibles.");
    }
    if (!state.functions.length) {
      throw new Error("No se encontró ninguna Function. Revisa Functions Read o el nombre en Samsara.");
    }
    unlockWorkspace();
    setStatus("status", "", "");
  } catch (error) {
    setStatus("gateStatus", error.message, "err");
  } finally {
    $("unlock").disabled = false;
  }
}

async function generate() {
  const vehicle = state.vehicles.find((item) => item.id === $("vehicle").value);
  const fn = selectedFunction();
  const start = $("start").value;
  const end = $("end").value;
  if (!state.unlocked || !token()) {
    lockWorkspace();
    return;
  }
  if (!fn) {
    setStatus("status", "Elige la Function que vas a correr.", "err");
    return;
  }
  if (!vehicle || !start || !end) {
    setStatus("status", "Elige unidad y ambas fechas.", "err");
    return;
  }
  if (end < start) {
    setStatus("status", "La fecha fin no puede ser anterior al inicio.", "err");
    return;
  }
  if (daySpan(start, end) > (state.config.maxRangeDays || 7)) {
    setStatus("status", `Máximo ${state.config.maxRangeDays || 7} días.`, "err");
    return;
  }
  $("generate").disabled = true;
  setStatus("status", `Lanzando ${fn.name} en Samsara…`);
  try {
    const correlationId = await startFunctionRun(apiRoot(), token(), fn.name, {
      vehicle_id: vehicle.id,
      start_time: start,
      end_time: end,
      api_key: token(),
      write_storage: "true",
      include_csv: "false",
    });
    setStatus("status", `${fn.name} en curso (${correlationId}). Esperando Storage…`);
    const run = await waitForFunctionRun(apiRoot(), token(), fn.name, correlationId);
    showResult({
      vehicle,
      start,
      end,
      correlationId,
      status: run.status,
      functionName: fn.name,
    });
    setStatus("status", `${fn.name} terminó. Ábrelo en Storage y descarga el archivo.`, "ok");
  } catch (error) {
    setStatus("status", error.message, "err");
    $("result").classList.remove("hidden");
    updateFunctionLinks();
  } finally {
    $("generate").disabled = false;
  }
}

$("filter").addEventListener("input", (event) => renderVehicles(event.target.value));
$("function").addEventListener("change", updateFunctionLinks);
$("unlock").addEventListener("click", unlock);
$("lock").addEventListener("click", lockWorkspace);
$("generate").addEventListener("click", generate);
$("token").addEventListener("keydown", (event) => {
  if (event.key === "Enter") unlock();
});
$("start").value = "2026-08-31";
$("end").value = "2026-08-31";

loadConfig().catch((error) => setStatus("gateStatus", error.message, "err"));
