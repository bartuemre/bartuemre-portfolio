"""Immutable runtime settings. Secrets are never part of the public status API."""

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit

from dotenv import dotenv_values


def boolean(value: str | None, name: str) -> bool:
    if value is None:
        return False
    if value.strip().lower() in {"true", "1", "yes", "on"}:
        return True
    if value.strip().lower() in {"false", "0", "no", "off", ""}:
        return False
    raise ValueError(f"{name} must be a boolean (true or false)")


@dataclass(frozen=True)
class Settings:
    database: str = "data/iprv.sqlite3"
    allow_external: bool = False
    allow_feed_downloads: bool = False
    auto_sync: bool = False
    frontend_origin: str = ""
    additional_frontend_origin: str = ""
    abuseipdb_key: str = field(default="", repr=False)
    threatfox_key: str = field(default="", repr=False)
    deployment: str = "local"
    public_host: str = ""
    access_token: str = field(default="", repr=False)
    ephemeral_storage: bool = False

    def __post_init__(self):
        if self.deployment not in {"local", "cloud"}:
            raise ValueError("IPRV_DEPLOYMENT must be local or cloud")
        if self.deployment == "local":
            for frontend_origin in (self.frontend_origin, self.additional_frontend_origin):
                if not frontend_origin:
                    continue
                origin = urlsplit(frontend_origin)
                local_origin = frontend_origin in {
                    "http://127.0.0.1:5173",
                    "http://localhost:5173",
                }
                public_origin = (
                    origin.scheme == "https"
                    and origin.hostname
                    and not origin.username
                    and not origin.password
                    and not origin.path
                    and not origin.query
                    and not origin.fragment
                    and frontend_origin == f"https://{origin.netloc}"
                )
                if not local_origin and not public_origin:
                    raise ValueError("IPRV_FRONTEND_ORIGIN must be a localhost or exact HTTPS origin")
            if self.access_token:
                raise ValueError("Access tokens require IPRV_DEPLOYMENT=cloud")
            return
        if not re.fullmatch(r"[a-z0-9](?:[a-z0-9.-]{0,251}[a-z0-9])?", self.public_host):
            raise ValueError("Cloud deployment requires an exact IPRV_PUBLIC_HOST hostname")
        if not 32 <= len(self.access_token) <= 256 or not all(
            33 <= ord(character) <= 126 for character in self.access_token
        ):
            raise ValueError("Cloud deployment requires a 32-256 character IPRV_ACCESS_TOKEN")
        for frontend_origin in (self.frontend_origin, self.additional_frontend_origin):
            if not frontend_origin:
                continue
            origin = urlsplit(frontend_origin)
            if (
                origin.scheme != "https"
                or not origin.hostname
                or origin.username is not None
                or origin.password is not None
                or origin.path
                or origin.query
                or origin.fragment
                or frontend_origin != f"https://{origin.netloc}"
                or not re.fullmatch(r"[a-z0-9][a-z0-9.-]*[a-z0-9]", origin.hostname)
            ):
                raise ValueError(
                    "Cloud deployment requires exact HTTPS frontend origins without paths"
                )
        if not self.frontend_origin:
            raise ValueError("Cloud deployment requires IPRV_FRONTEND_ORIGIN")

    @classmethod
    def load(cls, env_file: Path | None = None):
        config = {**dotenv_values(env_file or Path.cwd() / ".env"), **os.environ}
        origin = (config.get("IPRV_FRONTEND_ORIGIN") or "").rstrip("/")
        return cls(
            database=config.get("IPRV_DATABASE") or "data/iprv.sqlite3",
            allow_external=boolean(config.get("IPRV_ALLOW_EXTERNAL"), "IPRV_ALLOW_EXTERNAL"),
            allow_feed_downloads=boolean(
                config.get("IPRV_ALLOW_FEED_DOWNLOADS"), "IPRV_ALLOW_FEED_DOWNLOADS"
            ),
            auto_sync=boolean(config.get("IPRV_AUTO_SYNC"), "IPRV_AUTO_SYNC"),
            frontend_origin=origin,
            additional_frontend_origin=(config.get("IPRV_ADDITIONAL_FRONTEND_ORIGIN") or "").rstrip("/"),
            abuseipdb_key=(config.get("ABUSEIPDB_API_KEY") or "").strip(),
            threatfox_key=(config.get("THREATFOX_API_KEY") or "").strip(),
            deployment=config.get("IPRV_DEPLOYMENT") or "local",
            public_host=(
                config.get("IPRV_PUBLIC_HOST") or config.get("RENDER_EXTERNAL_HOSTNAME") or ""
            )
            .strip()
            .lower(),
            access_token=(config.get("IPRV_ACCESS_TOKEN") or "").strip(),
            ephemeral_storage=boolean(
                config.get("IPRV_EPHEMERAL_STORAGE"), "IPRV_EPHEMERAL_STORAGE"
            ),
        )
