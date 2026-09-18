# CEMEX — reporte de telemetría

El usuario final trabaja **en Samsara**, no en Streamlit ni en la terminal.

## Qué hace el cliente

1. En Samsara: **Functions** → `cemex-telemetry-report-ui` (o el nombre que tenga).
2. Revisa o cambia solo esto (Event parameters):
   - `vehicle_id` — unidad
   - `start_time` — primer día (`YYYY-MM-DD`)
   - `end_time` — último día incluido
3. **Ejecutar**.
4. **Storage** → `CEMEX_Reportes/{unidad}/` → descarga el CSV.

Eso es el informe de certificación. El script lee `api_key` de los Event parameters (Secrets vacío está bien), llama `GET /fleet/vehicles/stats/history` y arma el CSV.

**V1 (congelada):** 1 fila por minuto (1,440/día). Zip `cemex-telemetry-report-v1.zip`.  
**V2:** 1 fila cada 30 s (2,880/día). Zip `cemex-telemetry-report-v2.zip`. Handler `main.main`.

Parámetros fijos V2: `timezone=America/Mexico_City`, `granularity=30s`, `csv_dialect=es`, `write_storage=true`, `include_csv=false`, `storage_prefix=CEMEX_Reportes`.

Un día: `start_time` y `end_time` iguales. Siete días: p. ej. `2026-08-28` y `2026-09-03`. Máximo 7 días.

## Este repo

Código de las Functions. Para actualizar Samsara: sube el zip V1 o V2 (solo `src/`). No hace falta Streamlit Cloud.
