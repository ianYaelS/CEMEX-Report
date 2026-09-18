# Portal CEMEX

El cliente pega el **api_key** (solo esta sesión), elige unidad y fechas. La página invoca la Function **cemex-telemetry-report-ui** en Samsara (`POST /functions/{name}/runs`). El CSV se crea en Storage, no en GitHub.

Storage: [cemex-telemetry-report-ui](https://cloud.samsara.com/o/11006658/fleet/config/functions?view=storage&name=cemex-telemetry-report-ui)

Omar: no es SSH. Es la API de Functions. El token se pega a mano porque el repo es público.

## Token

Scopes: Read Vehicles, Read Vehicle Statistics, Functions Read, Functions Write. Nunca va en el repo.

## Local (relay incluido)

```bash
python web/server.py
```

Abre `http://127.0.0.1:8787`. El servidor solo reenvía a `api.samsara.com` y sirve el HTML. No guarda el token.

## GitHub Pages

`https://ianyaels.github.io/CEMEX-Report/` es la UI. El navegador **bloquea** llamadas directas a Samsara (CORS).

1. Corre el server local y trabaja en `127.0.0.1:8787`, o
2. Despliega `proxy/worker.js` (Cloudflare Worker) y pega esa URL en **Relay** (solo sesión) o en `web/config.json` → `proxyUrl`.

## Qué ve el cliente

1. Pega el token.
2. Carga unidades.
3. Elige fechas y **Generar en Samsara Storage**.
4. Abre Storage y busca el nombre que muestra la página. Descarga ahí y compara.
