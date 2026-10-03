# Copyright 2026 Seedian
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

"""Exceptions for the vendored Bejerman SOAP client.

Messages must not quote ErrorMsg, Token, xClave, credentials, or the WS URL.
"""

from __future__ import annotations


class BejermanError(Exception):
    """WS Resultado != OK or SOAP fault. Do not put ErrorMsg in the message."""

    def __init__(
        self,
        message: str = "",
        *,
        resultado: str | None = None,
    ) -> None:
        self.resultado = resultado
        super().__init__(message or "Bejerman WS error")


class BejermanConfigError(BejermanError):
    """Missing or invalid Settings."""


class BejermanInsecureTransportError(BejermanConfigError):
    """HTTP without bejerman_allow_insecure."""


class BejermanTransportError(BejermanError):
    """HTTP failure or unparseable SOAP."""
