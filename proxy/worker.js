/**
 * Relay público opcional: el token viaja en Authorization y no se guarda.
 * Deploy: wrangler deploy (Cloudflare Workers, gratis).
 */
const SAMSARA = "https://api.samsara.com";
const ALLOW_HEADERS = "Authorization, Content-Type, Accept, X-Samsara-Version";
const SAMSARA_VERSION = "2025-10-23";

function corsHeaders(origin) {
  return {
    "Access-Control-Allow-Origin": origin || "*",
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    "Access-Control-Allow-Headers": ALLOW_HEADERS,
    "Access-Control-Max-Age": "86400",
  };
}

export default {
  async fetch(request) {
    const origin = request.headers.get("Origin") || "*";
    if (request.method === "OPTIONS") {
      return new Response(null, { status: 204, headers: corsHeaders(origin) });
    }
    const url = new URL(request.url);
    const path = url.pathname.replace(/^\/samsara/, "") || "/";
    if (path === "/" || path === "/health") {
      return Response.json({ ok: true, relay: "samsara" }, { headers: corsHeaders(origin) });
    }
    const upstream = await fetch(`${SAMSARA}${path}${url.search}`, {
      method: request.method,
      headers: {
        Accept: "application/json",
        Authorization: request.headers.get("Authorization") || "",
        "X-Samsara-Version": request.headers.get("X-Samsara-Version") || SAMSARA_VERSION,
        ...(request.method !== "GET" ? { "Content-Type": "application/json" } : {}),
      },
      body: request.method === "GET" || request.method === "HEAD" ? undefined : await request.text(),
    });
    const body = await upstream.arrayBuffer();
    return new Response(body, {
      status: upstream.status,
      headers: {
        ...corsHeaders(origin),
        "Content-Type": upstream.headers.get("Content-Type") || "application/json",
        "Cache-Control": "no-store",
      },
    });
  },
};
