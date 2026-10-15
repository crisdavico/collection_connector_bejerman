# Copyright 2026 Seedian
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from unittest.mock import MagicMock, patch

import httpx

from odoo.tests import TransactionCase

from odoo.addons.collection_connector_bejerman.service.errors import (
    BejermanDeadlineError,
    BejermanError,
    BejermanTransportError,
)
from odoo.addons.collection_connector_bejerman.service.session import (
    BejermanClient,
    RetryPolicy,
)
from odoo.addons.collection_connector_bejerman.service.settings import (
    Credentials,
    Settings,
)

from .test_bejerman_connector import (
    _CIERRE_OK,
    _CLAVE,
    _CLIENTES,
    _REGISTRO_ERROR,
    _REGISTRO_OK,
    _SOAPACTION_CIERRE,
    _SOAPACTION_EJECUTAR,
    _SOAPACTION_REGISTRO,
    _WS_URL,
    BejermanTestMixin,
    _call_soap_action,
    _ejecutar_ok,
    _xml_response,
)

_SESSION = "odoo.addons.collection_connector_bejerman.service.session"
_CONNECTOR_LOGGER = (
    "odoo.addons.collection_connector_bejerman.models.collection_connector"
)


def _settings(**overrides):
    values = {
        "ws_url": _WS_URL,
        "credentials": Credentials(
            user="ADMIN", password=_CLAVE, company="MODE", workstation="1"
        ),
        "timeout": 60.0,
        "deadline": 900.0,
    }
    values.update(overrides)
    return Settings(**values)


def _status_response(status, headers=None):
    """A non-2xx answer shaped like httpx's (status, headers, raise_for_status)."""
    response = MagicMock()
    response.status_code = status
    response.headers = httpx.Headers(headers or {})
    response.content = b""
    request = httpx.Request("POST", _WS_URL)
    response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "status", request=request, response=httpx.Response(status, request=request)
    )
    return response


class _Clock:
    """Monotonic clock the test moves by hand."""

    def __init__(self, now=1000.0):
        self.now = now

    def __call__(self):
        return self.now


class _Script:
    """Answer each SOAP action from its own queue; record every POST."""

    def __init__(self, **queues):
        self.queues = {name: list(items) for name, items in queues.items()}
        self.calls = []

    def __call__(self, url, content=None, headers=None, **kwargs):
        action = headers["SOAPAction"].strip('"').rsplit("_WS", 1)[-1]
        self.calls.append((action, kwargs))
        queue = self.queues.get(action) or []
        item = queue.pop(0) if len(queue) > 1 else queue[0]
        if isinstance(item, Exception):
            raise item
        return item


def _ok_session(**overrides):
    queues = {
        "Registro": [_xml_response(_REGISTRO_OK)],
        "Ejecutar": [_xml_response(_ejecutar_ok(_CLIENTES))],
        "CierreProceso": [_xml_response(_CIERRE_OK)],
    }
    queues.update(overrides)
    return _Script(**queues)


class TestBejermanSessionRetry(TransactionCase):
    """Transient errors are retried within one deadline; nothing is left open."""

    def _client(self, script, settings=None, **kwargs):
        self.sleeps = []
        kwargs.setdefault("sleep", self.sleeps.append)
        kwargs.setdefault("rand", lambda: 1.0)
        client = BejermanClient(settings or _settings(), **kwargs)
        self.addCleanup(client._http.close)
        return client

    def _run(self, script, settings=None, **kwargs):
        client = self._client(script, settings, **kwargs)
        with patch(f"{_SESSION}.httpx.Client.post", side_effect=script):
            with client:
                return client.tablas.get_customers()

    def test_read_is_retried_after_a_timeout_then_succeeds(self):
        timeout = httpx.ReadTimeout("slow")
        script = _ok_session(Ejecutar=[timeout, _xml_response(_ejecutar_ok(_CLIENTES))])
        rows = self._run(script)
        self.assertEqual(len(rows), len(_CLIENTES))
        actions = [action for action, _kwargs in script.calls]
        self.assertEqual(actions, ["Registro", "Ejecutar", "Ejecutar", "CierreProceso"])
        self.assertEqual(self.sleeps, [1.0])

    def test_server_errors_back_off_exponentially_with_jitter(self):
        script = _ok_session(
            Ejecutar=[
                _status_response(502),
                _status_response(500),
                _xml_response(_ejecutar_ok(_CLIENTES)),
            ]
        )
        self._run(script, rand=lambda: 0.0)
        # Equal jitter: half the exponential ceiling, plus up to the other half.
        self.assertEqual(self.sleeps, [0.5, 1.0])

    def test_retry_after_is_honoured_and_capped(self):
        script = _ok_session(
            Ejecutar=[
                _status_response(429, {"Retry-After": "7"}),
                _status_response(503, {"Retry-After": "3600"}),
                _xml_response(_ejecutar_ok(_CLIENTES)),
            ]
        )
        self._run(script, settings=_settings(max_attempts=3))
        self.assertEqual(self.sleeps, [7.0, RetryPolicy().max_delay])

    def test_exhausted_retries_raise_a_transport_error(self):
        script = _ok_session(Ejecutar=[httpx.ConnectError("refused")])
        with self.assertRaises(BejermanTransportError):
            self._run(script)
        ejecutar = [call for call in script.calls if call[0] == "Ejecutar"]
        self.assertEqual(len(ejecutar), 3)
        self.assertEqual(len(self.sleeps), 2)
        self.assertEqual(script.calls[-1][0], "CierreProceso")

    def test_client_errors_are_not_retried(self):
        script = _ok_session(Ejecutar=[_status_response(400)])
        with self.assertRaises(BejermanTransportError):
            self._run(script)
        self.assertEqual(
            [call[0] for call in script.calls],
            ["Registro", "Ejecutar", "CierreProceso"],
        )
        self.assertEqual(self.sleeps, [])

    def test_login_is_retried_only_when_it_never_reached_the_server(self):
        refused = _ok_session(
            Registro=[httpx.ConnectError("refused"), _xml_response(_REGISTRO_OK)]
        )
        self._run(refused)
        self.assertEqual([c[0] for c in refused.calls][:2], ["Registro", "Registro"])

        ambiguous = _ok_session(Registro=[httpx.ReadTimeout("lost answer")])
        with self.assertRaises(BejermanTransportError):
            self._run(ambiguous)
        self.assertEqual([c[0] for c in ambiguous.calls], ["Registro"])

    def test_session_close_is_not_retried(self):
        script = _ok_session(CierreProceso=[httpx.ReadTimeout("slow")])
        with self.assertRaises(BejermanTransportError):
            self._run(script)
        self.assertEqual([c[0] for c in script.calls].count("CierreProceso"), 1)

    def test_each_request_timeout_is_capped_by_the_remaining_deadline(self):
        clock = _Clock()
        script = _ok_session()
        settings = _settings(timeout=60.0, deadline=100.0)
        client = self._client(script, settings, clock=clock)
        with patch(f"{_SESSION}.httpx.Client.post", side_effect=script):
            with client:
                clock.now += 90.0
                client.tablas.get_customers()
        timeouts = [kwargs["timeout"] for _action, kwargs in script.calls]
        self.assertEqual(timeouts[0].read, 60.0)
        self.assertAlmostEqual(timeouts[1].read, 10.0)

    def test_no_request_is_sent_past_the_deadline(self):
        clock = _Clock()
        script = _ok_session()
        client = self._client(script, _settings(deadline=100.0), clock=clock)
        with patch(f"{_SESSION}.httpx.Client.post", side_effect=script):
            with self.assertRaises(BejermanDeadlineError):
                with client:
                    clock.now += 101.0
                    client.tablas.get_customers()
        self.assertNotIn("Ejecutar", [call[0] for call in script.calls])

    def test_a_retry_that_would_pass_the_deadline_is_not_attempted(self):
        clock = _Clock()
        script = _ok_session(Ejecutar=[_status_response(429, {"Retry-After": "20"})])
        client = self._client(script, _settings(deadline=15.0), clock=clock)
        with patch(f"{_SESSION}.httpx.Client.post", side_effect=script):
            with self.assertRaises(BejermanDeadlineError):
                with client:
                    client.tablas.get_customers()
        self.assertEqual(self.sleeps, [])

    def test_a_trickling_answer_is_cut_at_the_deadline(self):
        """The body is read in chunks; the deadline is checked between them."""
        clock = _Clock()
        body = _REGISTRO_OK.encode("utf-8")

        def _trickle():
            for start in range(0, len(body), 64):
                clock.now += 30.0
                yield body[start : start + 64]

        def _handler(request):
            return httpx.Response(200, content=_trickle())

        client = self._client(
            None,
            _settings(deadline=100.0),
            clock=clock,
            transport=httpx.MockTransport(_handler),
        )
        with self.assertRaises(BejermanDeadlineError):
            with client:
                pass
        self.assertTrue(client._http.is_closed)

    def test_a_streamed_answer_within_the_deadline_is_read_whole(self):
        clock = _Clock()

        def _handler(request):
            action = request.headers["SOAPAction"]
            if "Registro" in action:
                text = _REGISTRO_OK
            elif "Cierre" in action:
                text = _CIERRE_OK
            else:
                text = _ejecutar_ok(_CLIENTES)
            body = text.encode("utf-8")
            return httpx.Response(200, content=iter([body[:100], body[100:]]))

        client = self._client(
            None, _settings(), clock=clock, transport=httpx.MockTransport(_handler)
        )
        with client:
            rows = client.tablas.get_customers()
        self.assertEqual(len(rows), len(_CLIENTES))

    def test_the_http_client_is_closed_when_login_fails(self):
        for answer in (
            _xml_response(_REGISTRO_ERROR),
            httpx.ReadTimeout("lost"),
            _status_response(401),
        ):
            with self.subTest(answer=type(answer).__name__):
                script = _ok_session(Registro=[answer])
                client = self._client(script)
                with patch(f"{_SESSION}.httpx.Client.post", side_effect=script):
                    with self.assertRaises(BejermanError):
                        with client:
                            pass
                self.assertTrue(client._http.is_closed)

    def test_retry_logs_carry_no_url_or_secret(self):
        script = _ok_session(
            Ejecutar=[
                httpx.ConnectError(f"refused {_WS_URL} {_CLAVE}"),
                _xml_response(_ejecutar_ok(_CLIENTES)),
            ]
        )
        with self.assertLogs(_SESSION, level="WARNING") as logs:
            self._run(script)
        blob = "\n".join(logs.output)
        self.assertNotIn(_WS_URL, blob)
        self.assertNotIn(_CLAVE, blob)
        self.assertIn("ConnectError", blob)


class TestBejermanRetryInTheRefresh(BejermanTestMixin, TransactionCase):
    """The connector refresh retries too, and records an exhausted one (T25)."""

    def test_refresh_survives_one_transient_error(self):
        connector = self._make_connector()
        script = _ok_session(
            Ejecutar=[
                _status_response(503),
                _xml_response(_ejecutar_ok(_CLIENTES)),
                _xml_response(_ejecutar_ok("[]")),
            ]
        )
        with (
            patch(f"{_SESSION}.httpx.Client.post", side_effect=script),
            patch(f"{_SESSION}._sleep") as sleep,
        ):
            connector._bejerman_refresh_snapshot()
        self.assertEqual(sleep.call_count, 1)
        self.assertEqual(connector.bejerman_snapshot_customer_count, 2)

    def test_exhausted_retries_are_recorded_as_a_connection_failure(self):
        connector = self._make_connector()
        script = _ok_session(Ejecutar=[httpx.ConnectError("refused")])
        with (
            patch(f"{_SESSION}.httpx.Client.post", side_effect=script),
            patch(f"{_SESSION}._sleep"),
            self.assertLogs(_CONNECTOR_LOGGER, level="WARNING"),
        ):
            self.env["collection.connector"]._bejerman_cron_refresh_snapshot()
        self.assertEqual(connector.bejerman_last_failure_reason, "connection")
        self.assertEqual(connector.bejerman_failure_count, 1)

    def test_deadline_is_recorded_as_a_timeout(self):
        connector = self._make_connector(bejerman_deadline=30)
        clock = _Clock()

        def _slow(url, content=None, headers=None, **kwargs):
            clock.now += 20.0
            return _erp_ok(headers)

        with (
            patch(f"{_SESSION}.httpx.Client.post", side_effect=_slow),
            patch(f"{_SESSION}._clock", new=clock),
            self.assertLogs(_CONNECTOR_LOGGER, level="WARNING"),
        ):
            self.env["collection.connector"]._bejerman_cron_refresh_snapshot()
        self.assertEqual(connector.bejerman_last_failure_reason, "timeout")

    def test_deadline_setting_is_admin_only_and_defaults_to_fifteen_minutes(self):
        connector = self._make_connector()
        self.assertEqual(connector.bejerman_deadline, 900)
        field = connector._fields["bejerman_deadline"]
        self.assertEqual(field.groups, "base.group_system")
        self.assertEqual(connector._bejerman_build_settings().deadline, 900.0)


def _erp_ok(headers):
    action = _call_soap_action(MagicMock(kwargs={"headers": headers}))
    if action == _SOAPACTION_REGISTRO:
        return _xml_response(_REGISTRO_OK)
    if action == _SOAPACTION_CIERRE:
        return _xml_response(_CIERRE_OK)
    assert action == _SOAPACTION_EJECUTAR
    return _xml_response(_ejecutar_ok(_CLIENTES))
