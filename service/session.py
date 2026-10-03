# Copyright 2026 Seedian
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

"""Registro → Ejecutar → CierreProceso. Token stays in memory; always Cierre."""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from .errors import BejermanError, BejermanTransportError
from .queries import QueriesOperations
from .settings import Settings
from .soap import (
    CONTENT_TYPE,
    SOAPACTION_CIERRE,
    SOAPACTION_EJECUTAR,
    SOAPACTION_REGISTRO,
    SoapResult,
    build_cierre,
    build_ejecutar,
    build_registro,
    parse_response,
    redact_soap,
)
from .tablas import TablasOperations

_logger = logging.getLogger(__name__)


class BejermanClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._token: str | None = None
        self._last_circuito = ""
        self._last_operacion = ""
        if settings.ssl_verify is False:
            _logger.warning("TLS certificate verification is disabled")
        if settings.allow_insecure and settings.ws_url.lower().startswith("http://"):
            _logger.warning("Using cleartext HTTP")
        self._http = httpx.Client(
            verify=settings.ssl_verify,
            timeout=settings.timeout,
        )
        self.tablas = TablasOperations(self)
        self.queries = QueriesOperations(self)

    def __enter__(self) -> BejermanClient:
        creds = self.settings.credentials
        envelope = build_registro(
            creds.usuario,
            creds.clave,
            creds.empresa,
            creds.puesto,
            creds.sucursal,
        )
        result = self._post(SOAPACTION_REGISTRO, envelope)
        _logger.info("Registro resultado=%s", result.resultado)
        self._raise_if_not_ok(result)
        self._token = result.token
        return self

    def execute(
        self,
        circuito: str,
        operacion: str,
        parametros_json: Any = None,
    ) -> Any:
        if not self._token:
            raise BejermanError(
                "Not registered; use BejermanClient as a context manager"
            )
        circuito = circuito.upper()
        payload = {} if parametros_json is None else parametros_json
        parametros_json_text = json.dumps(payload, ensure_ascii=False, default=str)
        self._last_circuito = circuito
        self._last_operacion = operacion
        envelope = build_ejecutar(
            circuito,
            operacion,
            parametros_json_text,
            self._token,
        )
        result = self._post(SOAPACTION_EJECUTAR, envelope)
        _logger.info(
            "Ejecutar circuito=%s operacion=%s resultado=%s",
            circuito,
            operacion,
            result.resultado,
        )
        self._raise_if_not_ok(result)
        if not result.datos_json:
            return None
        try:
            return json.loads(result.datos_json)
        except json.JSONDecodeError as exc:
            raise BejermanTransportError("DatosJSON is not valid JSON") from exc

    def close(self) -> None:
        self.__exit__(None, None, None)

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        try:
            if self._token is not None:
                try:
                    self._post_cierre()
                except Exception:
                    if exc_type is None:
                        raise
                    _logger.warning("CierreProceso failed during exception unwind")
        finally:
            self._token = None
            self._http.close()
        return None

    def _post_cierre(self) -> None:
        token = self._token
        if not token:
            return
        envelope = build_cierre(token, self._last_circuito, self._last_operacion)
        result = self._post(SOAPACTION_CIERRE, envelope)
        _logger.info(
            "CierreProceso circuito=%s operacion=%s resultado=%s",
            self._last_circuito,
            self._last_operacion,
            result.resultado,
        )
        self._raise_if_not_ok(result)

    def _post(self, soap_action: str, envelope: str) -> SoapResult:
        self._log_soap(soap_action, envelope)
        headers = {
            "Content-Type": CONTENT_TYPE,
            "SOAPAction": f'"{soap_action}"',
        }
        try:
            response = self._http.post(
                self.settings.ws_url,
                content=envelope.encode("utf-8"),
                headers=headers,
            )
            response.raise_for_status()
        except httpx.HTTPError:
            raise BejermanTransportError("Bejerman transport error") from None
        return parse_response(response.content)

    def _log_soap(self, soap_action: str, envelope: str) -> None:
        _logger.debug(
            "%s SOAP (redacted): %s",
            soap_action,
            redact_soap(envelope, self.settings.credentials.clave),
        )

    @staticmethod
    def _raise_if_not_ok(result: SoapResult) -> None:
        if (result.resultado or "").strip() == "OK":
            return
        raise BejermanError("Bejerman WS error", resultado=result.resultado)
