# CEMEX — reporte de telemetría

Portal (`web/`): token → Function → unidad → fechas. El CSV lo genera Samsara Storage.

Function: `cemex-telemetry-report-ui`  
Storage: [abrir en Samsara](https://cloud.samsara.com/o/11006658/fleet/config/functions?view=storage&name=cemex-telemetry-report-ui)

El token se pega en la sesión. No va en el repo.

Un día: inicio = fin. Máximo 7 días.

## Function

- **V1:** 1,440 filas/día. `cemex-telemetry-report-v1.zip`
- **V2:** 2,880 filas/día (30 s). `cemex-telemetry-report-v2.zip`. Handler `main.main`
