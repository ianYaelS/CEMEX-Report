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

export function apiCandidates(config) {
  const roots = [];
  const proxy = String(config.proxyUrl || "").trim().replace(/\/$/, "");
  if (proxy) roots.push(`${proxy}/samsara`);
  roots.push("/samsara");
  roots.push(String(config.apiBaseUrl || "https://api.samsara.com").replace(/\/$/, ""));
  return [...new Set(roots)];
}

export function resolveApiRoot(config) {
  return apiCandidates(config)[0];
}

function apiErrorMessage(status, payload, cors) {
  if (cors) {
    return "No se pudo conectar con Samsara. Revisa el token.";
  }
  if (status === 401) {
    return "Token inválido.";
  }
  if (status === 403) {
    return "El token no tiene permiso de Functions.";
  }
  if (status === 404) {
    const detail = payload?.message ? ` ${payload.message}` : "";
    return `Samsara no encontró esa Function.${detail}`.trim();
  }
  if (status === 429) {
    return "Samsara limita a 2 corridas por minuto. Espera e inténtalo de nuevo.";
  }
  const message = payload?.message || payload?.error || `HTTP ${status}`;
  return String(message);
}

export function functionPageUrl(orgId, name) {
  return `https://cloud.samsara.com/o/${orgId}/fleet/config/functions?name=${encodeURIComponent(name)}`;
}

export function functionStorageUrl(orgId, name) {
  return `https://cloud.samsara.com/o/${orgId}/fleet/config/functions?view=storage&name=${encodeURIComponent(name)}`;
}

export async function samsaraFetch(apiRoot, token, path, { method = "GET", body, ignoreStatuses = [] } = {}) {
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
    if (ignoreStatuses.includes(response.status)) return null;
    throw new Error(apiErrorMessage(response.status, payload, false));
  }
  return payload;
}

function functionFromPayload(payload, fallbackName = "") {
  const data = payload?.data && !Array.isArray(payload.data) ? payload.data : payload;
  const name = String(data?.name || fallbackName).trim();
  if (!name) return null;
  return {
    name,
    description: String(data.description || "").trim(),
  };
}

const MISSING_FUNCTION = [400, 403, 404, 405, 501];

export function configuredFunctions(candidates = []) {
  const names = [];
  const seen = new Set();
  for (const value of candidates) {
    const name = String(value || "").trim();
    if (!name || seen.has(name)) continue;
    seen.add(name);
    names.push({ name, description: "" });
  }
  return names;
}

export async function getFunction(apiRoot, token, name) {
  const payload = await samsaraFetch(apiRoot, token, `/functions/${encodeURIComponent(name)}`, {
    ignoreStatuses: MISSING_FUNCTION,
  });
  return payload ? functionFromPayload(payload, name) : null;
}

export async function listFunctions(apiRoot, token, candidates = []) {
  const found = new Map();
  const configured = configuredFunctions(candidates);
  try {
    const listed = await samsaraFetch(apiRoot, token, "/functions", { ignoreStatuses: MISSING_FUNCTION });
    const rows = Array.isArray(listed?.data) ? listed.data : [];
    for (const item of rows) {
      const parsed = functionFromPayload(item, item?.name);
      if (parsed) found.set(parsed.name, parsed);
    }
  } catch (_error) {
    // No hay listado público de Functions; usamos los nombres del portal.
  }
  await Promise.all(
    configured.map(async (item) => {
      if (found.has(item.name)) return;
      try {
        const parsed = await getFunction(apiRoot, token, item.name);
        found.set(item.name, parsed || item);
      } catch (_error) {
        found.set(item.name, item);
      }
    })
  );
  if (!found.size) {
    for (const item of configured) found.set(item.name, item);
  }
  return [...found.values()].sort((a, b) => a.name.localeCompare(b.name, "es"));
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

export async function connectSamsara(config, token) {
  const candidates = apiCandidates(config);
  let lastError = new Error("No se pudo conectar con Samsara. Revisa el token.");
  for (const root of candidates) {
    try {
      await samsaraFetch(root, token, "/fleet/vehicles?limit=1");
      return root;
    } catch (error) {
      lastError = error;
    }
  }
  throw lastError;
}

export async function startFunctionRun(apiRoot, token, functionName, paramsOverride) {
  try {
    const payload = await samsaraFetch(apiRoot, token, `/functions/${encodeURIComponent(functionName)}/runs`, {
      method: "POST",
      body: { paramsOverride },
    });
    const correlationId = payload?.data?.correlationId || payload?.correlationId;
    if (!correlationId) throw new Error("Samsara no devolvió correlationId.");
    return String(correlationId);
  } catch (error) {
    const text = String(error?.message || "");
    if (text.includes("no encontró") || text.includes("404")) {
      throw new Error(
        `La Function “${functionName}” no existe en esta org. Cópiala de Samsara → Functions.`
      );
    }
    throw error;
  }
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
