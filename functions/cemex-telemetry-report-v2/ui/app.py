"""Streamlit UI precargada con los Event parameters de la Function."""
from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "ui"))

from client import SamsaraClient
from constants import DEFAULT_API_BASE_URL, MAX_RANGE_DAYS, ROWS_PER_DAY
from defaults import load_function_defaults, resolve_api_key
from report_service import generate_ui_report
from vehicles import list_vehicles, vehicle_label


@st.cache_resource(show_spinner=False)
def _client(token: str) -> SamsaraClient:
    return SamsaraClient(DEFAULT_API_BASE_URL, token)


@st.cache_data(ttl=300, show_spinner=False)
def _fleet(token: str) -> list[dict[str, str]]:
    vehicles = list_vehicles(_client(token))
    return [
        {
            "id": vehicle.id,
            "name": vehicle.name,
            "license_plate": vehicle.license_plate,
            "label": vehicle_label(vehicle),
        }
        for vehicle in vehicles
    ]


def _matches(vehicle: dict[str, str], query: str) -> bool:
    needle = query.strip().lower()
    if not needle:
        return True
    haystack = " ".join(
        (vehicle["name"], vehicle["license_plate"], vehicle["id"], vehicle["label"])
    ).lower()
    return needle in haystack


def _index_for(options: list[dict[str, str]], vehicle_id: str) -> int:
    for index, item in enumerate(options):
        if item["id"] == vehicle_id:
            return index
    return 0


def _access_ok() -> bool:
    try:
        password = str(st.secrets.get("APP_PASSWORD", "") or "").strip()
    except Exception:
        password = ""
    if not password:
        return True
    if st.session_state.get("cemex_ok"):
        return True
    entered = st.text_input("Clave de acceso", type="password")
    if entered and entered == password:
        st.session_state["cemex_ok"] = True
        return True
    if entered:
        st.error("Clave incorrecta.")
    return False


def main() -> None:
    defaults = load_function_defaults()
    st.set_page_config(page_title="Reporte CEMEX", layout="centered")
    st.title("Reporte CEMEX")
    st.write("Elige la unidad y las fechas, genera el informe y descárgalo.")
    st.caption(
        f"{ROWS_PER_DAY:,} filas por día (cada 30 s) · {defaults['timezone']} · "
        f"máximo {MAX_RANGE_DAYS} días."
    )
    if not _access_ok():
        st.stop()

    token = resolve_api_key(secrets=getattr(st, "secrets", None))
    if not token:
        token = st.text_input("api_key", type="password").strip()

    left, right = st.columns(2)
    start_time = left.date_input(
        "start_time",
        value=defaults["start_time"],
        format="YYYY-MM-DD",
    )
    end_time = right.date_input(
        "end_time",
        value=defaults["end_time"],
        format="YYYY-MM-DD",
    )

    if not token:
        st.warning("Falta el api_key en los secretos del hosting. El cliente no debería ver esto.")
        st.stop()

    try:
        fleet = _fleet(token)
    except Exception as exc:
        st.error(f"No se pudo leer GET /fleet/vehicles: {exc}")
        st.stop()
    if not fleet:
        st.error("La org no devolvió unidades en /fleet/vehicles.")
        st.stop()

    query = st.text_input("Filtrar unidades", placeholder="nombre, placa o id")
    options = [item for item in fleet if _matches(item, query)]
    if not options:
        st.warning("Ninguna unidad coincide con el filtro.")
        st.stop()

    selected = st.selectbox(
        "Unidad",
        options,
        index=_index_for(options, defaults["vehicle_id"]),
        format_func=lambda item: item["label"],
        help="GET /fleet/vehicles: nombre, placa e id. Precarga vehicle_id de params.",
    )

    if start_time > end_time:
        st.error("end_time debe ser igual o posterior a start_time.")
        st.stop()
    if (end_time - start_time).days + 1 > MAX_RANGE_DAYS:
        st.error(f"El rango no puede pasar de {MAX_RANGE_DAYS} días.")
        st.stop()

    if st.button("Generar reporte", type="primary", use_container_width=True):
        try:
            with st.spinner("Consultando stats/history y armando la grilla de 30 s…"):
                generated = generate_ui_report(
                    token,
                    vehicle_id=selected["id"],
                    start_time=start_time,
                    end_time=end_time,
                    timezone=defaults["timezone"],
                    client=_client(token),
                )
            st.session_state["generated_report"] = generated
            plate = generated.license_plate or "sin placa"
            st.success(
                f"Listo {generated.vehicle_name} ({plate} · {generated.vehicle_id}) "
                f"{start_time.isoformat()} → {end_time.isoformat()}: "
                f"{generated.row_count:,} filas, {generated.validation_status}."
            )
        except Exception as exc:
            st.error(f"No se pudo generar el informe: {exc}")

    generated = st.session_state.get("generated_report")
    if not generated or generated.vehicle_id != selected["id"]:
        return

    st.download_button(
        "Descargar CSV",
        data=generated.csv_bytes,
        file_name=generated.filename,
        mime="text/csv",
        type="primary",
        use_container_width=True,
    )


if __name__ == "__main__":
    main()
