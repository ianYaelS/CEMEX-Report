const $ = (id) => document.getElementById(id);

const state = {
  vehicles: [],
  last: null,
  config: {
    storageUrl:
      "https://cloud.samsara.com/o/11006658/fleet/config/functions?view=storage&name=cemex-telemetry-report-ui",
  },
};

function todayIso() {
  return new Date().toISOString().slice(0, 10);
}

function setStatus(text, kind) {
  const node = $("status");
  node.textContent = text;
  node.className = `status ${kind || ""}`;
}

function token() {
  return $("token").value.trim();
}

function headers() {
  const out = { "Content-Type": "application/json" };
  if (token()) out["X-Api-Key"] = token();
  return out;
}

function downloadCsv(filename, csv) {
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
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
    empty.textContent = "Sin unidades para ese filtro";
    empty.value = "";
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

function showResult(payload) {
  state.last = payload;
  $("result").classList.remove("hidden");
  $("resultSummary").textContent =
    `${payload.filename} · ${payload.rowCount.toLocaleString("es-MX")} filas · ${payload.validationStatus} · ${payload.vehicleName}`;
  $("storagePath").textContent = `Ruta en Storage: ${payload.storageKey}`;
  $("storageLink").href = payload.storageUrl || state.config.storageUrl;
}

async function loadConfig() {
  try {
    const response = await fetch("/api/config");
    if (response.ok) {
      state.config = await response.json();
      $("storageLink").href = state.config.storageUrl;
      return;
    }
  } catch (_error) {
    /* GitHub Pages sirve solo estáticos */
  }
  const fallback = await fetch("./config.json");
  if (fallback.ok) state.config = await fallback.json();
  $("storageLink").href = state.config.storageUrl;
}

async function loadVehicles() {
  const response = await fetch("/api/vehicles", { headers: headers() });
  if (response.status === 404) {
    throw new Error(
      "Esta página en GitHub Pages es solo la interfaz. Para generar el CSV corre python web/server.py desde el repo (o despliega ese servidor)."
    );
  }
  const payload = await response.json();
  if (!response.ok) {
    if (response.status === 401) {
      $("tokenHint").classList.remove("hidden");
      $("token").classList.remove("hidden");
    }
    throw new Error(payload.error || "No se pudo listar la flota");
  }
  state.vehicles = payload.vehicles || [];
  renderVehicles($("filter").value);
}

async function generate() {
  const vehicleId = $("vehicle").value;
  const startTime = $("start").value;
  const endTime = $("end").value;
  if (!vehicleId || !startTime || !endTime) {
    setStatus("Selecciona unidad y ambas fechas.", "err");
    return;
  }
  $("generate").disabled = true;
  setStatus("Generando el informe con la misma lógica que la Function…");
  try {
    const response = await fetch("/api/report", {
      method: "POST",
      headers: headers(),
      body: JSON.stringify({
        vehicle_id: vehicleId,
        start_time: startTime,
        end_time: endTime,
      }),
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error || "Falló la generación");
    downloadCsv(payload.filename, payload.csv);
    showResult(payload);
    setStatus("CSV descargado. Ábrelo en Samsara Storage y compara ambos archivos.", "ok");
  } catch (error) {
    setStatus(error.message, "err");
  } finally {
    $("generate").disabled = false;
  }
}

$("filter").addEventListener("input", (event) => renderVehicles(event.target.value));
$("generate").addEventListener("click", generate);
$("downloadAgain").addEventListener("click", () => {
  if (state.last) downloadCsv(state.last.filename, state.last.csv);
});
$("start").value = "2026-08-31";
$("end").value = "2026-08-31";
if (!$("start").value) $("start").value = todayIso();

loadConfig()
  .then(loadVehicles)
  .catch((error) => setStatus(error.message, "err"));
