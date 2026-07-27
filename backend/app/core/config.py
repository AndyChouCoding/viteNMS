from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_ALLOWED_HOSTS = {"127.0.0.1", "localhost"}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="OVV_", env_file=".env")

    HOST: str = "127.0.0.1"
    PORT: int = 8756
    DEBUG: bool = False

    # Topology discovery (SNMP/LLDP/CDP + ARP) — see app/services/topology_builder.py
    SNMP_TIMEOUT_SECONDS: int = 2
    SNMP_MAX_HOPS: int = 3
    TOPOLOGY_POLL_INTERVAL_SECONDS: int = 60

    # Dev origins are the Vite dev server; packaged origins are Tauri's webview.
    # Confirm the exact packaged origin against the installed Tauri version
    # before shipping — it differs by platform/WebView (see plan risks).
    CORS_ORIGINS: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "tauri://localhost",
        "https://tauri.localhost",
    ]

    @field_validator("HOST")
    @classmethod
    def host_must_be_loopback(cls, v: str) -> str:
        if v not in _ALLOWED_HOSTS:
            raise ValueError(
                f"HOST must be a loopback address {_ALLOWED_HOSTS}, got {v!r}. "
                "This backend is not designed to be exposed beyond localhost."
            )
        return v


settings = Settings()
