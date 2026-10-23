# Copyright 2026 Seedian
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from unittest.mock import patch

import httpx

from odoo.exceptions import UserError
from odoo.tests import TransactionCase

from .common import (
    _CLAVE,
    _ERROR_MSG,
    _SESSION_TOKEN,
    _SOAPACTION_CIERRE,
    _WS_URL,
    _call_body,
    _call_soap_action,
)
from .test_bejerman_connector import (
    BejermanTestMixin,
    _patch_httpx,
)

_SERVICE_SESSION = "odoo.addons.collection_connector_bejerman.service.session"
_CONNECTOR_LOGGER = (
    "odoo.addons.collection_connector_bejerman.models.collection_connector"
)
_HOST = "erp.secret.example"
_SECRETS = (
    _CLAVE,
    _SESSION_TOKEN,
    _ERROR_MSG,
    _WS_URL,
    "ErrorMsg",
    "xClave",
    "Envelope",
    "SOAP",
)
_LOGIN_MSG = (
    "Bejerman rejected the login. Check the user, password, company and workstation."
)
_CUSTOMERS_MSG = "Connected to Bejerman, but the customer list could not be read."


class TestBejermanTestConnection(BejermanTestMixin, TransactionCase):
    """Test Connection names the failing stage without leaking secrets."""

    def _fail_message(self, connector):
        with self.assertRaises(UserError) as ctx:
            connector._bejerman_test_connection()
        message = str(ctx.exception)
        for secret in _SECRETS:
            self.assertNotIn(secret, message)
        return message

    def test_success(self):
        connector = self._make_connector()
        with _patch_httpx() as mock_post:
            self.assertIs(connector._bejerman_test_connection(), True)
        actions = [_call_soap_action(call) for call in mock_post.call_args_list]
        self.assertEqual(len(actions), 3)
        self.assertEqual(actions[-1], _SOAPACTION_CIERRE)
        bodies = [_call_body(call) for call in mock_post.call_args_list]
        self.assertFalse(any("ObtenerJsonQueryVista" in body for body in bodies))

    def test_missing_settings_are_named(self):
        connector = self._make_connector(bejerman_ws_url="", bejerman_clave="")
        with _patch_httpx() as mock_post:
            message = self._fail_message(connector)
        self.assertEqual(
            message,
            "The Bejerman connector is not configured. "
            "Missing settings: Bejerman WS URL, Bejerman Password.",
        )
        mock_post.assert_not_called()

    def test_invalid_settings_reason(self):
        connector = self._make_connector(
            bejerman_ws_url="http://erp.secret.example/leaky-ws"
        )
        with _patch_httpx() as mock_post:
            message = self._fail_message(connector)
        self.assertEqual(
            message,
            "The Bejerman settings are not valid: "
            "HTTP requires bejerman_allow_insecure.",
        )
        self.assertNotIn("leaky-ws", message)
        mock_post.assert_not_called()

    def test_transport_failure_names_host_only(self):
        connector = self._make_connector()

        def _boom(_url, content=None, headers=None, **_kwargs):
            raise httpx.ConnectError(
                f"connect {_WS_URL} user=ADMIN clave={_CLAVE} Token={_SESSION_TOKEN}"
            )

        with (
            patch(f"{_SERVICE_SESSION}.httpx.Client.post", side_effect=_boom),
            # Connect errors are retried (T26); the test must not sleep.
            patch(f"{_SERVICE_SESSION}._sleep"),
        ):
            message = self._fail_message(connector)
        self.assertEqual(
            message,
            f"Could not reach the Bejerman server at {_HOST}. "
            "Check the WS URL, the network connection and the certificate settings.",
        )
        self.assertNotIn("Bejerman-SDK-WS", message)

    def test_login_rejected(self):
        connector = self._make_connector()
        with _patch_httpx(fail=("Registro",)) as mock_post:
            message = self._fail_message(connector)
        self.assertEqual(message, _LOGIN_MSG)
        self.assertEqual(mock_post.call_count, 1)

    def test_customers_failure(self):
        connector = self._make_connector()
        with _patch_httpx(fail=("ObtenerClientes",)) as mock_post:
            message = self._fail_message(connector)
        self.assertEqual(message, _CUSTOMERS_MSG)
        actions = [_call_soap_action(call) for call in mock_post.call_args_list]
        self.assertEqual(actions[-1], _SOAPACTION_CIERRE)

    def test_failure_log_has_class_name_only(self):
        connector = self._make_connector()
        with _patch_httpx(fail=("Registro",)):
            with self.assertLogs(_CONNECTOR_LOGGER, level="WARNING") as captured:
                with self.assertRaises(UserError):
                    connector._bejerman_test_connection()
        blob = "\n".join(captured.output)
        self.assertIn("BejermanError", blob)
        for secret in _SECRETS:
            self.assertNotIn(secret, blob)
