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

## GitHub Pages vs app desbloqueable

`https://ianyaels.github.io/CEMEX-Report/` muestra la llave (token). El navegador **bloquea** `api.samsara.com` (CORS), así que el desbloqueo real se hace así:

1. Local: `python web/server.py` → `http://127.0.0.1:8787` (mismo UI, sí llama a Samsara).
2. Público desde este GitHub: [Importar el repo en Netlify](https://app.netlify.com/start/deploy?repository=https://github.com/ianYaelS/CEMEX-Report) (login con GitHub). Queda `/samsara` en el mismo dominio: pegas el token, carga la flota y corre la Function.

## Qué ve el cliente

1. Pega el token.
2. Carga unidades.
3. Elige fechas y **Generar en Samsara Storage**.
4. Abre Storage y busca el nombre que muestra la página. Descarga ahí y compara.
