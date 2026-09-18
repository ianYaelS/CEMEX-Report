# CEMEX telemetría V2 — grilla de 30 segundos

V1 (minuto a minuto) quedó congelada en `functions/cemex-telemetry-report-v1` y `cemex-telemetry-report-v1.zip`. Esta carpeta es **V2**.

El informe sigue siendo el CSV de certificación CEMEX de **una unidad** (GPS + motor + odómetro OBD) en `America/Mexico_City`. La diferencia es la frecuencia de salida: **00:00:00, 00:00:30, 00:01:00, 00:01:30… hasta 23:59:30**. Un día = **2,880** filas; siete días = **20,160**. La API no se llama cada 30 s: se pide **una vez** `GET /fleet/vehicles/stats/history` del rango (más 24 h de lookback) y el script alinea cada punto a su slot de 30 s. Si el slot no trajo GPS, arrastra el último conocido. No interpola.

El catálogo de unidades sale de **GET /fleet/vehicles** (paginado): nombre, placa (`licensePlate`) e id. Eso alimenta el dropdown de Streamlit. El reporte en sí usa el `vehicle_id` elegido y `GET /fleet/vehicles/{id}` (si 404, sigue con el id). Types de history: `gps,engineStates,obdOdometerMeters`. Nunca `gpsOdometerMeters`. Motor: On → Encendido, Idle → Ralentí, Off → Apagado.

CSV igual que V1: UTF-8 con BOM, `;`, QUOTE_ALL, mismos headers. Storage: `CEMEX_Reportes/{unidad}/{fecha}_{id}_{nombre}.csv` más `_auditoria.json`.

**Function.** Sube `cemex-telemetry-report-v2.zip` (solo `src/`, handler `main.main`). Event parameters: `vehicle_id`, `start_time`, `end_time`, `timezone=America/Mexico_City`, `granularity=30s`, `csv_dialect=es`, `write_storage=true`, `api_key`. `codeVersion`: `cemex-30s-v2-2026-09-17`.

**Para el cliente:** una URL. No instala nada. Elige unidad, fechas, Generar, Descargar.

Tú lo publicas una vez en [share.streamlit.io](https://share.streamlit.io): sube este repo a GitHub, Create app, archivo `streamlit_app.py`, Python 3.12. En Advanced settings → Secrets:

```toml
api_key = "samsara_api_xxx"
APP_PASSWORD = "clave-corta-para-cemex"
```

El token no lo ve el cliente. Le mandas solo el enlace `https://….streamlit.app`.

Functions sigue siendo el camino de certificación (Run → Storage). Streamlit Cloud es la pantalla del usuario final.

```bash
PYTHONPATH=functions/cemex-telemetry-report-v2/src .venv12/bin/python -m pytest functions/cemex-telemetry-report-v2/tests -q
```
