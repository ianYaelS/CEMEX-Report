export function sanitizeSegment(value, fallback = "unidad") {
  let cleaned = String(value || "")
    .trim()
    .split("")
    .map((ch) => (/[A-Za-z0-9_-]/.test(ch) ? ch : "_"))
    .join("");
  while (cleaned.includes("__")) cleaned = cleaned.split("__").join("_");
  cleaned = cleaned.replace(/^[._]+|[._]+$/g, "");
  return cleaned || fallback;
}

export function expectedStorageKey({ prefix, vehicleId, vehicleName, startDate, endDate }) {
  const root = sanitizeSegment(prefix || "CEMEX_Reportes", "CEMEX_Reportes");
  const unitId = sanitizeSegment(vehicleId, "sinid");
  const unitName = sanitizeSegment(vehicleName, unitId);
  const folder = unitName === "unidad" ? unitId : unitName;
  const stamp = startDate === endDate ? startDate : `${startDate}_a_${endDate}`;
  const filename = `${stamp}_${unitId}_${unitName}.csv`;
  return { storageKey: `${root}/${folder}/${filename}`, filename };
}

export function vehicleLabel(vehicle) {
  return `${vehicle.name} · ${vehicle.licensePlate || "sin placa"} · ${vehicle.id}`;
}

function isLocalHost(hostname) {
  return hostname === "127.0.0.1" || hostname === "localhost";
}

export function resolveApiRoot(config, locationLike = window.location) {
  const proxy = String(config.proxyUrl || "").trim().replace(/\/$/, "");
  if (proxy) return `${proxy}/samsara`;
  if (isLocalHost(locationLike.hostname)) return "/samsara";
  return String(config.apiBaseUrl || "https://api.samsara.com").replace(/\/$/, "");
}

function apiErrorMessage(status, payload, cors) {
  if (cors) {
    return "El navegador bloqueó api.samsara.com (CORS). Esta página pública necesita el relay del repo (python web/server.py) o la URL del proxy en la sesión.";
  }
  if (status === 401) {
    return "Token inválido. Pega el api_key de esta org (Read Vehicles + Read/Write Functions).";
  }
  if (status === 403) {
    return "El token no tiene permiso de Functions. Agrégale Functions Read y Write.";
  }
  if (status === 404) {
    return "No está la Function cemex-telemetry-report-ui en esta org.";
  }
  if (status === 429) {
    return "Samsara limita a 2 corridas por minuto. Espera e inténtalo de nuevo.";
  }
  const message = payload?.message || payload?.error || `HTTP ${status}`;
  return String(message);
}

export async function samsaraFetch(apiRoot, token, path, { method = "GET", body } = {}) {
  const url = `${apiRoot}${path.startsWith("/") ? path : `/${path}`}`;
  let response;
  try {
    response = await fetch(url, {
      method,
      headers: {
        Accept: "application/json",
        Authorization: `Bearer ${token}`,
        ...(body ? { "Content-Type": "application/json" } : {}),
      },
      body: body ? JSON.stringify(body) : undefined,
    });
  } catch (error) {
    const cors = String(error?.message || "").toLowerCase().includes("fetch");
    throw new Error(apiErrorMessage(0, null, cors));
  }
  let payload = {};
  try {
    payload = await response.json();
  } catch (_error) {
    payload = {};
  }
  if (!response.ok) {
    throw new Error(apiErrorMessage(response.status, payload, false));
  }
  return payload;
}

export async function listVehicles(apiRoot, token) {
  const vehicles = [];
  const seen = new Set();
  let after = "";
  for (let page = 0; page < 40; page += 1) {
    const query = after ? `?after=${encodeURIComponent(after)}` : "";
    const payload = await samsaraFetch(apiRoot, token, `/fleet/vehicles${query}`);
    const rows = Array.isArray(payload.data) ? payload.data : [];
    for (const item of rows) {
      const id = String(item?.id || "").trim();
      if (!id || seen.has(id)) continue;
      seen.add(id);
      vehicles.push({
        id,
        name: String(item.name || id).trim(),
        licensePlate: String(item.licensePlate || item.license_plate || "").trim(),
      });
    }
    vehicles.sort((a, b) => a.name.localeCompare(b.name, "es") || a.id.localeCompare(b.id));
    const pagination = payload.pagination || {};
    if (!pagination.hasNextPage || !pagination.endCursor) break;
    after = String(pagination.endCursor);
  }
  return vehicles.map((item) => ({ ...item, label: vehicleLabel(item) }));
}

export async function startFunctionRun(apiRoot, token, functionName, paramsOverride) {
  const payload = await samsaraFetch(apiRoot, token, `/functions/${encodeURIComponent(functionName)}/runs`, {
    method: "POST",
    body: { paramsOverride },
  });
  const correlationId = payload?.data?.correlationId || payload?.correlationId;
  if (!correlationId) throw new Error("Samsara no devolvió correlationId.");
  return String(correlationId);
}

export async function getFunctionRun(apiRoot, token, functionName, correlationId) {
  const payload = await samsaraFetch(
    apiRoot,
    token,
    `/functions/${encodeURIComponent(functionName)}/runs/${encodeURIComponent(correlationId)}`
  );
  return payload?.data || payload;
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

export async function waitForFunctionRun(apiRoot, token, functionName, correlationId, { timeoutMs = 90000 } = {}) {
  const started = Date.now();
  let last = { status: "started" };
  while (Date.now() - started < timeoutMs) {
    last = await getFunctionRun(apiRoot, token, functionName, correlationId);
    const status = String(last.status || "").toLowerCase();
    if (status === "success") return last;
    if (status === "error" || status === "timeout" || status === "dropped") {
      throw new Error(`La Function terminó en ${status}. Revisa Logs en Samsara.`);
    }
    await sleep(2000);
  }
  throw new Error("La Function sigue corriendo. Ábrela en Samsara Storage / Logs con este correlationId.");
}
