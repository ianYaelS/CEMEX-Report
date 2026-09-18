#!/bin/zsh
set -euo pipefail
cd "$(dirname "$0")"

if [[ -x .venv12/bin/python ]]; then
  PY=".venv12/bin/python"
elif [[ -x .venv/bin/python ]]; then
  PY=".venv/bin/python"
else
  PY="python3"
fi

"$PY" -c "import requests" 2>/dev/null || "$PY" -m pip install -r web/requirements.txt

if [[ -z "${api_key:-}" && -z "${SAMSARA_API_TOKEN:-}" ]]; then
  TOKEN="$(osascript -e 'Tell application "System Events" to display dialog "Pega el api_key de la Function (Event parameters). Solo se usa en esta sesión." default answer "" with hidden answer with title "Informe CEMEX"' -e 'text returned of result' || true)"
  if [[ -z "${TOKEN}" ]]; then
    osascript -e 'display dialog "Sin api_key no se puede abrir el informe." buttons {"OK"} with title "Informe CEMEX"'
    exit 1
  fi
  export api_key="${TOKEN}"
fi

PORT="${PORT:-8787}"
open "http://127.0.0.1:${PORT}"
exec "$PY" web/server.py
