const SAMSARA = "https://api.samsara.com";

const cors = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "Authorization, Content-Type, Accept",
  "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
  "Cache-Control": "no-store",
};

exports.handler = async (event) => {
  if (event.httpMethod === "OPTIONS") {
    return { statusCode: 204, headers: cors, body: "" };
  }
  const suffix = (event.path || "").replace(/^\/samsara/, "").replace(/^\/\.netlify\/functions\/samsara/, "") || "/";
  const query = event.rawQuery ? `?${event.rawQuery}` : "";
  const upstream = await fetch(`${SAMSARA}${suffix}${query}`, {
    method: event.httpMethod,
    headers: {
      Accept: "application/json",
      Authorization: event.headers.authorization || event.headers.Authorization || "",
      ...(event.body ? { "Content-Type": "application/json" } : {}),
    },
    body: event.httpMethod === "GET" || event.httpMethod === "HEAD" ? undefined : event.body,
  });
  return {
    statusCode: upstream.status,
    headers: { ...cors, "Content-Type": upstream.headers.get("content-type") || "application/json" },
    body: await upstream.text(),
  };
};
