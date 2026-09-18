# Portal CEMEX

El cliente entra aquí: elige unidad, filtra fechas, descarga el CSV y abre Storage de Samsara para comparar el archivo.

La lógica del informe es la Function V2 (`functions/cemex-telemetry-report-v2`). Esta carpeta solo la expone.

Storage: [cemex-telemetry-report-ui](https://cloud.samsara.com/o/11006658/fleet/config/functions?view=storage&name=cemex-telemetry-report-ui)

## Local

```bash
export api_key="…"   # el mismo Event parameter de la Function
python web/server.py
```

Abre `http://127.0.0.1:8787`. El token también puede ir en `SAMSARA_API_TOKEN`. Si el servidor no lo tiene, el cliente lo pega en la sesión (no se guarda).

## GitHub

1. Sube este repo.
2. En el repo: **Settings → Pages → GitHub Actions**. El workflow `.github/workflows/pages.yml` publica `web/`.
3. GitHub Pages sirve la interfaz (unidad, fechas, enlace a Storage).
4. Para generar y descargar el CSV hace falta el servidor (`web/server.py`): mismo repo, en tu máquina o en un host que apunte a este GitHub. El token va en la variable de entorno `api_key`, nunca en el frontend ni en el repo.

## Qué ve el cliente

1. Busca y selecciona la unidad.
2. Pone fecha inicio y fin (mismo día = 24 h; máximo 7 días).
3. **Generar y descargar CSV**.
4. El mensaje le dice que el archivo también está en Storage de Samsara.
5. **Abrir Storage en Samsara** → busca el mismo nombre que descargó y compara.
