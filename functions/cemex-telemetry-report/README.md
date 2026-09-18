# Integración CEMEX — reporte de telemetría diario (V1)

**V1 confirmada y congelada.** El zip histórico es `cemex-telemetry-report-v1.zip`. La V2 (30 s + Streamlit) vive en `functions/cemex-telemetry-report-v2`.

Function de Samsara + CLI local. Genera el **CSV de certificación CEMEX** de una unidad, minuto a minuto, en zona `America/Mexico_City`. Lo guarda en **Functions Storage** para descargarlo como archivo.

**Function:** `cemex-telemetry-report`  
**Handler:** `main.main`  
**Versión:** `cemex-idle-audit-2026-09-16`

Corridas de referencia (FAV68 `281475002878096`):

| Corrida | Rango | Resultado |
| --- | --- | --- |
| `9fd14ba9-…` | 31-ago-2026 | 1,440 filas, `VALID`, 0 gaps, 1,227 minutos arrastrados |
| `73a63b41-…` | 28-ago → 03-sep-2026 | 10,080 filas, `VALID`, 0 gaps, un CSV + una auditoría |

## Qué es y qué no es

Es un export de **GPS + estado de motor + odómetro OBD** alineado a una grilla fija de 1 minuto.

No es:

- Dashboard *Rep1*
- Detailed Vehicle Activity
- Reporte de viajes (inicio/fin, velocidad máxima, km de viaje)
- El poll de “Consulta GPS unidades espejos” (ventanas de ~3 min, flota completa)

La API `/fleet/vehicles/stats/history` **no entrega un punto por minuto**. En movimiento manda ~cada 5 s; en parado, heartbeat (~1/hora o ~cada 5 min). El script arma la grilla CEMEX y, si un minuto no tiene GPS nativo, **arrastra el último conocido**. No interpola ruta ni inventa coordenadas.

## Flujo

```text
Event parameters (+ api_key)
        ↓
Function main.main
        ↓
GET /fleet/vehicles/{id}  (si 404, sigue con el id)
        ↓
GET /fleet/vehicles/stats/history
    types = gps,engineStates,obdOdometerMeters
    start = start_time − 24 h   (lookback)
    end   = medianoche siguiente al end_time
        ↓
Por cada día local: 1,440 minutos
    mismo minuto → último GPS (last_gps_by_timestamp)
    minuto sin GPS → last_known_carry
        ↓
Un CSV + una auditoría en Functions Storage
```

`types` son **exactamente 3**. Un cuarto type rompe el endpoint. Nunca se pide ni se lee `gpsOdometerMeters`.

## Contrato del CSV

- UTF-8 **con BOM**
- Delimitador **`;`** (Excel México)
- Campos entrecomillados (`QUOTE_ALL`) para que las comas del header de motor no partan columnas
- Una fila por minuto local: 1 día = **1,440**; 7 días = **10,080**
- `start` inclusivo (`00:00:00`), `end` exclusivo (medianoche del día siguiente)
- Primera fila del día: `00:00:00`. Última: `23:59:00`

Headers ES (exactos, no traducir):

1. `Fecha y hora`
2. `Estado de motor (Encendido, Apagado, Ralentí)`
3. `Velocidad de vehiculo en Km/hr`
4. `Latitud GPS`
5. `Longitud GPS`
6. `Odómetro en Km`
7. `Nombre de dirección de posición basado en GPS`

### Cómo se llena cada columna

| Columna | Origen |
| --- | --- |
| Fecha y hora | Minuto local `YYYY-MM-DD HH:MM:SS` en `timezone` |
| Motor | `engineStates` as-of al final del minuto. `On` / `On (Driving)` → `Encendido`. `Idle` / `On (Idle)` → `Ralentí`. `Off` o vacío → `Apagado`. El return trae `engine.idleCheck`: si la API mandó Idle y el CSV no tiene Ralentí, el día queda `INVALIDO/PENDIENTE` |
| Velocidad | `gps.speedMilesPerHour × 1.609344`, 2 decimales. No se usa `ecuSpeedMph` |
| Lat / Lon | Último GPS de ese minuto, o el último conocido si el minuto iba vacío. 6 decimales |
| Odómetro | `obdOdometerMeters / 1000`, 2 decimales. El primer OBD del rango se arrastra hacia atrás; luego as-of |
| Dirección | `reverseGeo.formattedLocation` (o `address.name` si no hay reverse geo) |

## Cómo se cubren los huecos

1. Lookback de **24 h** antes de `start_time` para sembrar las 00:00.
2. Varios GPS en el mismo minuto: se queda el **último** (`last_gps_by_timestamp`). Los demás van a `collapsedMinutes` y **no invalidan**.
3. Minuto sin GPS: se copia lat, lon, velocidad, dirección y se recalcula motor/odo as-of (`last_known_carry`).
4. Si no hay lookback, los minutos de madrugada se rellenan desde el primer GPS del día.
5. **No** se interpola entre dos puntos.
6. `gaps[]` / `INVALIDO/PENDIENTE` solo si no hay ningún GPS en lookback + rango (celdas que no se pudieron llenar).

Un día parado (p. ej. 30-ago FAV68: 25 GPS nativos) sale con 1,440 filas continuas en el patio. La auditoría indica `nativeMinuteCount` vs `carriedMinuteCount`.

## Storage

Cada corrida escribe **dos** objetos (el rango completo, no un archivo por día):

```text
CEMEX_Reportes/{unidad}/{fecha}_{vehicleId}_{unidad}.csv
CEMEX_Reportes/{unidad}/{fecha}_{vehicleId}_{unidad}_auditoria.json
```

Ejemplos:

```text
CEMEX_Reportes/FAV68/2026-08-31_281475002878096_FAV68.csv
CEMEX_Reportes/FAV68/2026-08-28_a_2026-09-03_281475002878096_FAV68.csv
```

Misma unidad + mismo periodo **sobrescribe**. Functions no tiene “Save as” en el Run; el archivo se baja de la pestaña **Storage**.

Descarga en Excel: UTF-8, delimitador `;`.

## Event parameters

Todas son **string**. No crees `SamsaraFunctionTriggerSource` (Samsara lo inyecta solo).

### Obligatorios en certificación

| Key | Ejemplo | Qué hace |
| --- | --- | --- |
| `vehicle_id` | `281475002878096` | ID Samsara de la unidad. No uses el nombre. Si el catálogo da 404, el script igual pide stats con ese id |
| `start_time` | `2026-08-31` | Primer día local, inclusivo (`00:00`) |
| `end_time` | `2026-08-31` | Último día local **incluido**. Si es solo fecha, cubre ese día hasta la medianoche siguiente (exclusiva) |
| `timezone` | `America/Mexico_City` | Zona IANA de la grilla |
| `granularity` | `minute` | `minute` = grilla CEMEX. `native` / `second` son modos extra, no el entregable |
| `csv_dialect` | `es` | `es` = headers y `;` CEMEX. `en` traduce. `tracking` es el CSV 24 h nativo (coma, sin BOM) |
| `write_storage` | `true` | Escribe CSV + auditoría en Storage |
| `include_csv` | `false` | Si `true`, el return mete el CSV crudo (no usar en dashboard) |
| `storage_prefix` | `CEMEX_Reportes` | Carpeta raíz en Storage |
| `api_key` | `samsara_api_…` | Token de **esta** org, lectura de Vehicle Statistics. No va en el zip. El runtime a menudo no inyecta Secrets; por eso vive como Event parameter. También acepta `SAMSARA_API_TOKEN` / `SAMSARA_KEY` / `apiKey`. **Nunca se loguea** |

### Fechas

| Caso | `start_time` | `end_time` | Filas |
| --- | --- | --- | ---: |
| Un día | `2026-08-31` | `2026-08-31` | 1,440 |
| 7 días, 31-ago al inicio | `2026-08-31` | `2026-09-06` | 10,080 |
| 7 días, 31-ago al centro | `2026-08-28` | `2026-09-03` | 10,080 |

Máximo **7 días** (`end − start ≤ 7`). Timeout de Functions ~15 min.

También vale RFC3339 (`2026-08-31T00:00:00-06:00`). Solo `report_date=2026-08-31` equivale a un día. Sin fechas → **ayer** en `timezone`.

### Opcionales

| Key | Default | Notas |
| --- | --- | --- |
| `vehicle_name` | — | Solo si no hay `vehicle_id` |
| `api_base_url` | `https://api.samsara.com` | Solo `https` |

Samsara siempre manda `SamsaraFunctionTriggerSource` y `SamsaraFunctionCorrelationId`. Se loguean; no se configuran.

## Return de la Function

Un día (validado):

```json
{
  "ok": true,
  "statusCode": 200,
  "codeVersion": "cemex-single-file-2026-09-16",
  "validationStatus": "VALID",
  "rowCount": 1440,
  "dayCount": 1,
  "dailyRowCounts": { "2026-08-31": 1440 },
  "gapCount": 0,
  "carriedMinuteCount": 1227,
  "collapsedMinuteCount": 147,
  "fillRule": "last_known_carry",
  "storageKey": "CEMEX_Reportes/FAV68/2026-08-31_281475002878096_FAV68.csv"
}
```

Siete días: `rowCount=10080`, `dayCount=7`, cada `dailyRowCounts[día]=1440`, un solo `dailyFiles[]`.

`rowCount` se valida contra **días × 1,440**, no contra 1,440 fijo.

## Auditoría

JSON hermano del CSV. Un día trae checks de grilla, `carriedRanges` y `collapsedMinutes`. Varios días traen resumen por día (`nativeMinuteCount`, `carriedMinuteCount`, `dailyStatus`) sin un JSON por día.

## Cómo correrlo

1. Subir `cemex-telemetry-report.zip` (solo el contenido de `src/`, handler `main.main`).
2. Poner Event parameters (tabla de arriba).
3. Run.
4. Storage → `CEMEX_Reportes/{unidad}/` → descargar el CSV.

```bash
mkdir -p functions/cemex-telemetry-report/dist
cd functions/cemex-telemetry-report/src
zip -r ../dist/cemex-telemetry-report.zip . -x '*__pycache__*' '*.pyc'
```

El runtime de Functions ya trae `requests` y `tenacity`. No empaquetar `.venv`.

## CLI local (misma lógica)

```bash
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export SAMSARA_API_TOKEN=samsara_api_xxx
python3 cli.py \
  --vehicle-id 281475002878096 \
  --start-time 2026-08-31 \
  --end-time 2026-08-31 \
  --timezone America/Mexico_City \
  --output out/CEMEX_FAV68_2026-08-31.csv
```

## Tests

```bash
PYTHONPATH=functions/cemex-telemetry-report/src python3.12 -m pytest tests -q
```

Sin red. Cubren grilla 1,440 / 10,080, factor 1.609344, OBD vs GPS odometer, un solo archivo en rangos, y arrastre de huecos.

## Límites

- Una unidad por corrida.
- Máximo 7 días.
- El CSV “lleno” no significa 1,440 pings reales. Mira `nativeMinuteCount`.
- El token debe ser de la **misma org** que el `vehicle_id`.
- Mismo path en Storage se sobrescribe; los CSV diarios de versiones viejas hay que borrarlos a mano.
