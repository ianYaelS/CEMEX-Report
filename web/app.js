import {
  expectedStorageKey,
  listVehicles,
  resolveApiRoot,
  startFunctionRun,
  waitForFunctionRun,
} from "./samsara.js";

const $ = (id) => document.getElementById(id);

const state = {
  vehicles: [],
  config: {
    functionName: "cemex-telemetry-report-ui",
    apiBaseUrl: "https://api.samsara.com",
    proxyUrl: "",
    storagePrefix: "CEMEX_Reportes",
    storageUrl:
      "https://cloud.samsara.com/o/11006658/fleet/config/functions?view=storage&name=cemex-telemetry-report-ui",
    functionUrl: "https://cloud.samsara.com/o/11006658/fleet/config/functions?name=cemex-telemetry-report-ui",
    maxRangeDays: 7,
  },
};

function setStatus(text, kind) {
  const node = $("status");
  node.textContent = text;
  node.className = `status ${kind || ""}`;
}

function token() {
  return $("token").value.trim();
}

function sessionProxy() {
  return $("proxy").value.trim();
}

function apiRoot() {
  return resolveApiRoot({ ...state.config, proxyUrl: sessionProxy() || state.config.proxyUrl });
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
    empty.textContent = state.vehicles.length ? "Sin unidades para ese filtro" : "Carga la flota con el token";
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

function showResult({ vehicle, start, end, correlationId, status }) {
  const keys = expectedStorageKey({
    prefix: state.config.storagePrefix,
    vehicleId: vehicle.id,
    vehicleName: vehicle.name,
    startDate: start,
    endDate: end,
  });
  $("result").classList.remove("hidden");
  $("resultSummary").textContent =
    `Function ${state.config.functionName} · ${status || "success"} · ${vehicle.name}`;
  $("storagePath").textContent = `Archivo en Storage: ${keys.storageKey}`;
  $("correlation").textContent = `correlationId: ${correlationId}`;
  $("storageLink").href = state.config.storageUrl;
  $("functionLink").href = state.config.functionUrl;
}

async function loadConfig() {
  const response = await fetch("./config.json", { cache: "no-store" });
  if (response.ok) state.config = { ...state.config, ...(await response.json()) };
  $("storageLink").href = state.config.storageUrl;
  $("functionLink").href = state.config.functionUrl;
  if (state.config.proxyUrl) $("proxy").value = state.config.proxyUrl;
}

async function loadFleet() {
  if (!token()) {
    setStatus("Pega el api_key de esta sesión.", "err");
    $("token").focus();
    return;
  }
  $("loadFleet").disabled = true;
  setStatus("Leyendo la flota en Samsara…");
  try {
    state.vehicles = await listVehicles(apiRoot(), token());
    renderVehicles($("filter").value);
    setStatus(`${state.vehicles.length} unidades. Elige una y genera el reporte en Samsara.`, "ok");
  } catch (error) {
    setStatus(error.message, "err");
  } finally {
    $("loadFleet").disabled = false;
  }
}

async function generate() {
  const vehicle = state.vehicles.find((item) => item.id === $("vehicle").value);
  const start = $("start").value;
  const end = $("end").value;
  if (!token()) {
    setStatus("Pega el api_key de esta sesión.", "err");
    return;
  }
  if (!vehicle || !start || !end) {
    setStatus("Carga la flota, elige unidad y ambas fechas.", "err");
    return;
  }
  if (end < start) {
    setStatus("La fecha fin no puede ser anterior al inicio.", "err");
    return;
  }
  const days = daySpan(start, end);
  if (days > (state.config.maxRangeDays || 7)) {
    setStatus(`Máximo ${state.config.maxRangeDays || 7} días.`, "err");
    return;
  }
  $("generate").disabled = true;
  setStatus("Invocando cemex-telemetry-report-ui en Samsara…");
  try {
    const correlationId = await startFunctionRun(apiRoot(), token(), state.config.functionName, {
      vehicle_id: vehicle.id,
      start_time: start,
      end_time: end,
      api_key: token(),
      write_storage: "true",
      include_csv: "false",
    });
    setStatus(`Function en curso (${correlationId}). Esperando Storage…`);
    const run = await waitForFunctionRun(apiRoot(), token(), state.config.functionName, correlationId);
    showResult({ vehicle, start, end, correlationId, status: run.status });
    setStatus("Listo en Samsara Storage. Ábrelo y busca el archivo para descargarlo y compararlo.", "ok");
  } catch (error) {
    setStatus(error.message, "err");
    $("result").classList.remove("hidden");
    $("storageLink").href = state.config.storageUrl;
    $("functionLink").href = state.config.functionUrl;
  } finally {
    $("generate").disabled = false;
  }
}

$("filter").addEventListener("input", (event) => renderVehicles(event.target.value));
$("loadFleet").addEventListener("click", loadFleet);
$("generate").addEventListener("click", generate);
$("token").addEventListener("keydown", (event) => {
  if (event.key === "Enter") loadFleet();
});
$("start").value = "2026-08-31";
$("end").value = "2026-08-31";

loadConfig().catch((error) => setStatus(error.message, "err"));
