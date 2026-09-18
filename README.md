# CEMEX — reporte de telemetría

El cliente usa el **portal** (`web/`): pega el api_key (no se guarda), elige unidad y fecha. Eso **dispara la Function en Samsara**. El CSV nace en Storage, no en GitHub.

Function: `cemex-telemetry-report-ui`  
Storage: [abrir en Samsara](https://cloud.samsara.com/o/11006658/fleet/config/functions?view=storage&name=cemex-telemetry-report-ui)

La invocación es `POST https://api.samsara.com/functions/cemex-telemetry-report-ui/runs` (API de Functions, no SSH). Token a mano porque el repo es público.

## Cliente

1. Pega el API token como llave → **Desbloquear y cargar unidades**.
2. Elige unidad y fechas → **Generar en Samsara Storage**.
3. En Storage busca el archivo y descárgalo ahí.

Local: `python web/server.py` → `http://127.0.0.1:8787`.  
Público desde este GitHub: [Netlify (importar el repo)](https://app.netlify.com/start/deploy?repository=https://github.com/ianYaelS/CEMEX-Report) — github.io solo es la UI; el navegador bloquea Samsara ahí.

Un día: inicio = fin. Siete días: p. ej. `2026-08-28` y `2026-09-03`. Máximo 7 días.

## Function (Samsara)

- **V1 (congelada):** 1,440 filas/día. Zip `cemex-telemetry-report-v1.zip`.
- **V2:** 2,880 filas/día (30 s). Zip `cemex-telemetry-report-v2.zip`. Handler `main.main`.

Parámetros fijos V2: `timezone=America/Mexico_City`, `granularity=30s`, `csv_dialect=es`, `write_storage=true`, `include_csv=false`, `storage_prefix=CEMEX_Reportes`.
