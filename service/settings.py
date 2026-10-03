# Copyright 2026 Seedian
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

"""Record-shaped Settings. No dotenv. One bejerman_allow_insecure flag."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from .errors import BejermanConfigError, BejermanInsecureTransportError


def _redacted_repr(cls_name: str, **fields: object) -> str:
    parts = ", ".join(f"{key}={value!r}" for key, value in fields.items())
    return f"{cls_name}({parts})"


def _validate_ws_url(url: str, allow_insecure: bool) -> None:
    parsed = urlparse(url)
    scheme = (parsed.scheme or "").lower()
    host = (parsed.hostname or "").lower()
    if scheme == "https":
        if not host:
            raise BejermanConfigError("WS URL has no hostname")
        return
    if scheme == "http":
        if not host:
            raise BejermanConfigError("WS URL has no hostname")
        if allow_insecure:
            return
        raise BejermanInsecureTransportError("HTTP requires bejerman_allow_insecure")
    raise BejermanConfigError("Unsupported URL scheme; use https")


@dataclass
class Credentials:
    usuario: str
    clave: str
    empresa: str
    puesto: str
    sucursal: str = ""

    def __post_init__(self) -> None:
        self.usuario = (self.usuario or "").upper()
        self.empresa = (self.empresa or "").upper()
        self.puesto = (self.puesto or "").upper()
        if self.sucursal is None:
            self.sucursal = ""

    def __repr__(self) -> str:
        return _redacted_repr(
            type(self).__name__,
            usuario=self.usuario,
            clave="***",
            empresa=self.empresa,
            puesto=self.puesto,
            sucursal=self.sucursal,
        )

    def __str__(self) -> str:
        return self.__repr__()


@dataclass
class Settings:
    """SOAP settings built from connector fields (Phase 3), not from env."""

    ws_url: str
    credentials: Credentials
    timeout: float = 60.0
    allow_insecure: bool = False
    ca_bundle: str = ""

    def __post_init__(self) -> None:
        _validate_ws_url(self.ws_url, self.allow_insecure)
        self.ca_bundle = (self.ca_bundle or "").strip()
        if self.ca_bundle:
            path = Path(self.ca_bundle)
            if not path.is_file():
                raise BejermanConfigError("CA bundle is not a readable file")

    @property
    def ssl_verify(self) -> bool | str:
        if self.ca_bundle:
            return str(Path(self.ca_bundle))
        if self.allow_insecure:
            return False
        return True

    @property
    def usuario(self) -> str:
        return self.credentials.usuario

    @property
    def empresa(self) -> str:
        return self.credentials.empresa

    @property
    def puesto(self) -> str:
        return self.credentials.puesto

    @property
    def sucursal(self) -> str:
        return self.credentials.sucursal

    def __repr__(self) -> str:
        return _redacted_repr(
            type(self).__name__,
            ws_url="***",
            credentials=self.credentials,
            timeout=self.timeout,
            allow_insecure=self.allow_insecure,
            ca_bundle="***" if self.ca_bundle else "",
        )

    def __str__(self) -> str:
        return self.__repr__()
