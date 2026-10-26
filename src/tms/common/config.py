"""Settings come from environment variables so the same build runs anywhere (TMS-NF-008)."""
from __future__ import annotations

import os
from dataclasses import dataclass


def _flag(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    database_url: str = "sqlite:///./tms.db"
    sensor_api_key: str = "sensor-demo-key"
    autotick: bool = True          # background loop that advances signals once a second
    seed_demo: bool = True         # create demo users and one intersection when the DB is empty
    token_hours: int = 8
    tls_cert: str = "certs/tms-cert.pem"
    tls_key: str = "certs/tms-key.pem"


def get_settings() -> Settings:
    return Settings(
        database_url=os.getenv("TMS_DATABASE_URL", "sqlite:///./tms.db"),
        sensor_api_key=os.getenv("TMS_SENSOR_API_KEY", "sensor-demo-key"),
        autotick=_flag("TMS_AUTOTICK", True),
        seed_demo=_flag("TMS_SEED_DEMO", True),
        token_hours=int(os.getenv("TMS_TOKEN_HOURS", "8")),
        tls_cert=os.getenv("TMS_TLS_CERT", "certs/tms-cert.pem"),
        tls_key=os.getenv("TMS_TLS_KEY", "certs/tms-key.pem"),
    )


# Default configuration of one intersection (see SAD 4.4 and SRS TMS-F-019).
DEFAULT_INTERSECTION_CONFIG: dict = {
    "approaches": {"N": "NS", "S": "NS", "E": "EW", "W": "EW"},  # approach -> signal phase
    "phases": ["NS", "EW"],
    "cycle_seconds": 90,
    "min_green": 10,
    "max_green": 60,
    "yellow": 3,
    "all_red": 2,
    "pedestrian_walk": 7,
    "pedestrian_clearance": 15,
    "count_interval_seconds": 60,
    "density_window_minutes": 5,
}
