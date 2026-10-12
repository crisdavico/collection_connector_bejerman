# Copyright 2026 Seedian
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

"""Registro → Ejecutar → CierreProceso. Token stays in memory; always Cierre.

Transient failures are retried with exponential backoff and jitter, within one
wall-clock deadline for the whole session:

- reads (the Ejecutar operations in ``IDEMPOTENT_OPERATIONS``) on connect
  errors, timeouts, dropped connections, HTTP 429 and 5xx;
- Registro only when the server cannot have processed it (connect errors,
  HTTP 429 and 503), so a lost answer never leaves a second ERP session open;
- CierreProceso never.

The deadline caps each request's timeout and is checked between the chunks of
every answer, so a slowly trickling download is cut instead of hanging.
"""

from __future__ import annotations

import json
import logging
import random
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any

import httpx

from .errors import BejermanDeadlineError, BejermanError, BejermanTransportError
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

# Read-only Ejecutar operations: sending one twice changes nothing in the ERP.
IDEMPOTENT_OPERATIONS = frozenset(
    {
        ("TABLAS", "OBTENERCLIENTES"),
        ("QUERIES", "OBTENERJSONQUERYVISTA"),
    }
)
# Errors raised before the request left this host.
_NOT_SENT_ERRORS = (httpx.ConnectError, httpx.ConnectTimeout)
# Transient network failures; the request may or may not have been processed.
_TRANSIENT_ERRORS = (
    httpx.TimeoutException,
    httpx.NetworkError,
    httpx.RemoteProtocolError,
)
# Answers that say the request was not processed.
_NOT_PROCESSED_STATUSES = frozenset({429, 503})
# Timeout of CierreProceso once the deadline is spent: the session is still
# closed, briefly, so the ERP does not keep it open.
_CLOSE_GRACE_SECONDS = 10.0

_NO_RETRY = "none"
_RETRY_NOT_SENT = "not_sent"
_RETRY_IDEMPOTENT = "idempotent"


def _sleep(seconds: float) -> None:
    time.sleep(seconds)


def _clock() -> float:
    return time.monotonic()


@dataclass(frozen=True)
class RetryPolicy:
    """Backoff between attempts; ``Settings.max_attempts`` bounds their number."""

    base_delay: float = 1.0
    max_delay: float = 30.0


class _DeadlineStream(httpx.SyncByteStream):
    """Answer body that checks the session deadline between chunks."""

    def __init__(self, stream: Any, check: Callable[[], None]) -> None:
        self._stream = stream
        self._check = check

    def __iter__(self) -> Iterator[bytes]:
        for chunk in self._stream:
            self._check()
            yield chunk

    def close(self) -> None:
        close = getattr(self._stream, "close", None)
        if close:
            close()


class BejermanClient:
    def __init__(
        self,
        settings: Settings,
        *,
        sleep: Callable[[float], None] | None = None,
        clock: Callable[[], float] | None = None,
        rand: Callable[[], float] | None = None,
        transport: httpx.BaseTransport | None = None,
        policy: RetryPolicy | None = None,
    ) -> None:
        self.settings = settings
        # Injectable so tests never sleep; module functions are read at call
        # time so they can be patched too.
        self._sleep = sleep
        self._clock = clock
        self._rand = rand
        self._policy = policy or RetryPolicy()
        self._closing = False
        self._deadline_at = self._now() + settings.deadline
        self._token: str | None = None
        self._last_circuito = ""
        self._last_operacion = ""
        if settings.ssl_verify is False:
            _logger.warning("TLS certificate verification is disabled")
        if settings.allow_insecure and settings.ws_url.lower().startswith("http://"):
            _logger.warning("Using cleartext HTTP")
        client_options = {
            "verify": settings.ssl_verify,
            "timeout": settings.timeout,
            "event_hooks": {"response": [self._guard_body]},
        }
        if transport is not None:
            client_options["transport"] = transport
        self._http = httpx.Client(**client_options)
        self.tablas = TablasOperations(self)
        self.queries = QueriesOperations(self)

    def __enter__(self) -> BejermanClient:
        try:
            creds = self.settings.credentials
            envelope = build_registro(
                creds.usuario,
                creds.clave,
                creds.empresa,
                creds.puesto,
                creds.sucursal,
            )
            result = self._post(SOAPACTION_REGISTRO, envelope, _RETRY_NOT_SENT)
            _logger.info("Registro resultado=%s", result.resultado)
            self._raise_if_not_ok(result)
            self._token = result.token
        except BaseException:
            # `with` never calls __exit__ when __enter__ fails.
            self._http.close()
            raise
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
        retry = (
            _RETRY_IDEMPOTENT
            if (circuito, operacion.upper()) in IDEMPOTENT_OPERATIONS
            else _NO_RETRY
        )
        result = self._post(SOAPACTION_EJECUTAR, envelope, retry)
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
        self._closing = True
        try:
            result = self._post(SOAPACTION_CIERRE, envelope, _NO_RETRY)
        finally:
            self._closing = False
        _logger.info(
            "CierreProceso circuito=%s operacion=%s resultado=%s",
            self._last_circuito,
            self._last_operacion,
            result.resultado,
        )
        self._raise_if_not_ok(result)

    def _post(self, soap_action: str, envelope: str, retry: str) -> SoapResult:
        self._log_soap(soap_action, envelope)
        headers = {
            "Content-Type": CONTENT_TYPE,
            "SOAPAction": f'"{soap_action}"',
        }
        attempt = 0
        while True:
            attempt += 1
            retry_after = None
            try:
                response = self._http.post(
                    self.settings.ws_url,
                    content=envelope.encode("utf-8"),
                    headers=headers,
                    timeout=self._request_timeout(),
                )
            except httpx.HTTPError as exc:
                if not self._may_retry(retry, attempt, error=exc):
                    raise BejermanTransportError("Bejerman transport error") from None
                failure = type(exc).__name__
            else:
                status = response.status_code
                if status == 429 or 500 <= status <= 599:
                    if not self._may_retry(retry, attempt, status=status):
                        raise BejermanTransportError("Bejerman transport error")
                    failure = f"HTTP {status}"
                    retry_after = response.headers.get("Retry-After")
                else:
                    try:
                        response.raise_for_status()
                    except httpx.HTTPError:
                        raise BejermanTransportError(
                            "Bejerman transport error"
                        ) from None
                    return parse_response(response.content)
            self._pause(attempt, failure, retry_after)

    def _may_retry(
        self,
        retry: str,
        attempt: int,
        error: Exception | None = None,
        status: int | None = None,
    ) -> bool:
        if attempt >= self.settings.max_attempts:
            return False
        if retry == _RETRY_IDEMPOTENT:
            return error is None or isinstance(error, _TRANSIENT_ERRORS)
        if retry == _RETRY_NOT_SENT:
            if error is not None:
                return isinstance(error, _NOT_SENT_ERRORS)
            return status in _NOT_PROCESSED_STATUSES
        return False

    def _pause(self, attempt: int, failure: str, retry_after: Any) -> None:
        """Wait before the next attempt, or give up if it would pass the deadline."""
        delay = self._retry_after_seconds(retry_after)
        if delay is None:
            policy = self._policy
            ceiling = min(policy.max_delay, policy.base_delay * 2 ** (attempt - 1))
            delay = ceiling / 2 + self._random() * ceiling / 2
        if delay >= self._deadline_at - self._now():
            raise BejermanDeadlineError("Bejerman deadline reached")
        _logger.warning(
            "Bejerman request failed (%s), attempt %s of %s; retrying in %.1f s",
            failure,
            attempt,
            self.settings.max_attempts,
            delay,
        )
        (self._sleep or _sleep)(delay)

    def _retry_after_seconds(self, value: Any) -> float | None:
        """Seconds asked by a sane Retry-After header, capped; else None."""
        text = str(value or "").strip()
        if not text:
            return None
        try:
            seconds = float(text)
        except ValueError:
            try:
                when = parsedate_to_datetime(text)
            except (TypeError, ValueError):
                return None
            if when.tzinfo is None:
                when = when.replace(tzinfo=timezone.utc)
            seconds = (when - datetime.now(timezone.utc)).total_seconds()
            seconds = max(seconds, 0.0)
        if seconds != seconds or seconds < 0:  # NaN or negative: not sane
            return None
        return min(seconds, self._policy.max_delay)

    def _request_timeout(self) -> httpx.Timeout:
        """Per-request timeout, never past the session deadline."""
        remaining = self._deadline_at - self._now()
        if self._closing:
            return httpx.Timeout(
                min(self.settings.timeout, max(remaining, _CLOSE_GRACE_SECONDS))
            )
        if remaining <= 0:
            raise BejermanDeadlineError("Bejerman deadline reached")
        return httpx.Timeout(min(self.settings.timeout, remaining))

    def _guard_body(self, response: httpx.Response) -> None:
        """Response hook: read the body through the deadline check."""
        response.stream = _DeadlineStream(response.stream, self._check_deadline)

    def _check_deadline(self) -> None:
        if not self._closing and self._now() > self._deadline_at:
            raise BejermanDeadlineError("Bejerman deadline reached")

    def _now(self) -> float:
        return (self._clock or _clock)()

    def _random(self) -> float:
        if self._rand is not None:
            return self._rand()
        # Jitter only spreads retries; it needs no cryptographic randomness.
        return random.random()  # noqa: S311

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
