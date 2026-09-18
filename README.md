# CEMEX — reporte de telemetría

El cliente usa el **portal web** (`web/`): elige la unidad, filtra la fecha, descarga el CSV y abre Storage de Samsara para comparar el archivo.

Storage de la Function: [cemex-telemetry-report-ui](https://cloud.samsara.com/o/11006658/fleet/config/functions?view=storage&name=cemex-telemetry-report-ui)

## Cliente

1. Abre el portal (`python web/server.py` o la URL de GitHub Pages + servidor).
2. Selecciona la unidad y el rango (`start_time` / `end_time`, `YYYY-MM-DD`).
3. Descarga el CSV.
4. En la misma pantalla: **Abrir Storage en Samsara** y busca el archivo con el mismo nombre.

Un día: inicio y fin iguales. Siete días: p. ej. `2026-08-28` y `2026-09-03`. Máximo 7 días.

## Function (Samsara)

El CSV lo arma `GET /fleet/vehicles/stats/history` (gps + engineStates + obdOdometerMeters). El `api_key` va en Event parameters.

- **V1 (congelada):** 1 fila por minuto (1,440/día). Zip `cemex-telemetry-report-v1.zip`.
- **V2:** 1 fila cada 30 s (2,880/día). Zip `cemex-telemetry-report-v2.zip`. Handler `main.main`.

Parámetros fijos V2: `timezone=America/Mexico_City`, `granularity=30s`, `csv_dialect=es`, `write_storage=true`, `include_csv=false`, `storage_prefix=CEMEX_Reportes`.

Para actualizar Samsara: sube el zip V1 o V2 (solo `src/`).

## Este repo

- `web/` — portal para el cliente y para deploy en GitHub (Pages = UI; `web/server.py` = generar/descargar).
- `functions/cemex-telemetry-report-v2/` — lógica del informe.
- `Abrir-informe-CEMEX.command` — abre el portal en esta Mac.
