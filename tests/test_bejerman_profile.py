# Copyright 2026 Seedian
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from unittest.mock import patch

from odoo.exceptions import UserError
from odoo.tests import TransactionCase

from odoo.addons.collection_connector_bejerman.service import mapping

from .common import (
    _NO_DEBT_SOURCE,
    _SOAPACTION_CIERRE,
    _SOAPACTION_REGISTRO,
    BejermanTestMixin,
    _call_body,
    _call_soap_action,
    _patch_httpx,
    _patch_today,
)

_DEBTS = [
    {
        "external_invoice_id": "FA|0001|A|00000042",
        "number": "FA A 0001-00000042",
        "customer_code": "123",
        "seller_code": "E",
        "issue_date": "2026-01-10",
        "due_date": "2026-02-10",
        "amount": 1000.0,
        "balance": 400.0,
        "document_kind": "invoice",
    },
]
_SELLERS = [{"seller_code": "E", "name": "Ana Seller"}]


def _profile_source(connector, client, today, stats):
    """A profile's debt source: real TABLAS customers, canned debt and sellers."""
    customers = [
        dict(row, credit_total=25.0 if row["customer_code"] == "123" else 0.0)
        for row in mapping.map_customer_rows(client.tablas.get_customers())
    ]
    stats["unparsable_amounts"] = 2
    return customers, [dict(row) for row in _DEBTS], [dict(row) for row in _SELLERS]


class TestBejermanProfile(BejermanTestMixin, TransactionCase):
    """The base reads customers only; the connector's profile reads the debt."""

    def _with_source(self, connector):
        model = type(connector)
        return (
            patch.object(model, "_bejerman_check_snapshot_source", new=lambda _s: None),
            patch.object(model, "_bejerman_read_snapshot", new=_profile_source),
        )

    def _refresh_with_source(self, connector):
        check, read = self._with_source(connector)
        with check, read, _patch_httpx() as mock_post:
            connector._bejerman_refresh_snapshot()
        return mock_post

    def test_new_connector_has_the_standard_profile(self):
        connector = self._make_connector()
        self.assertEqual(connector.bejerman_profile, "standard")
        field = connector._fields["bejerman_profile"]
        keys = {value for value, _label in field._description_selection(self.env)}
        self.assertIn("standard", keys)

    def test_standard_refresh_fails_closed_without_a_call(self):
        """No debt source: a configuration error, no session, snapshot kept."""
        connector = self._make_connector()
        self._refresh_with_source(connector)
        refreshed_at = connector.bejerman_snapshot_refreshed_at
        with _patch_httpx() as mock_post, self.assertRaises(UserError) as ctx:
            connector._bejerman_refresh_snapshot()
        self.assertEqual(str(ctx.exception), _NO_DEBT_SOURCE)
        self._assert_no_leak(str(ctx.exception))
        mock_post.assert_not_called()
        self.assertEqual(connector.bejerman_snapshot_refreshed_at, refreshed_at)
        debts = self.env["collection.connector.bejerman.debt"].search(
            [("connector_id", "=", connector.id)]
        )
        self.assertEqual(len(debts), 1)

    def test_cron_records_a_standard_connector_as_misconfigured(self):
        connector = self._make_connector()
        with _patch_httpx() as mock_post:
            self.env["collection.connector"]._bejerman_cron_refresh_snapshot()
        mock_post.assert_not_called()
        self.assertEqual(connector.bejerman_last_failure_reason, "configuration")
        self.assertEqual(connector.bejerman_failure_count, 1)

    def test_profile_source_drives_the_snapshot_in_one_session(self):
        connector = self._make_connector()
        mock_post = self._refresh_with_source(connector)
        actions = [_call_soap_action(call) for call in mock_post.call_args_list]
        self.assertEqual(actions[0], _SOAPACTION_REGISTRO)
        self.assertEqual(actions[-1], _SOAPACTION_CIERRE)
        self.assertEqual(len(actions), 3)
        self.assertIn("ObtenerClientes", _call_body(mock_post.call_args_list[1]))
        self.assertEqual(connector.bejerman_snapshot_customer_count, 2)
        self.assertEqual(connector.bejerman_snapshot_debt_count, 1)
        self.assertEqual(connector.bejerman_snapshot_skipped_count, 2)
        self.assertEqual(connector.bejerman_failure_count, 0)
        sellers = connector._bejerman_list_sellers()
        self.assertEqual(
            [(row["id"], row["name"]) for row in sellers], [("E", "Ana Seller")]
        )
        customers = connector._bejerman_list_customers("E")
        self.assertEqual([row["customer_code"] for row in customers], ["123"])

    def test_standard_debt_has_no_untaxed_amount_and_pays_on_the_total(self):
        """No `amount_untaxed`: `collection` falls back to the total."""
        connector = self._make_connector()
        self._refresh_with_source(connector)
        with _patch_today(connector):
            raw = connector._bejerman_get_customer_debt("E", "20123456789")
        self.assertEqual(raw["credit_total"], 25.0)
        self.assertEqual(len(raw["invoices"]), 1)
        self.assertNotIn("amount_untaxed", raw["invoices"][0])
        formatted = connector._format_customer_debt(raw)
        invoice = formatted["invoices"][0]
        self.assertEqual(invoice["amount_untaxed"], invoice["amount"])

    def test_erp_reflected_since_is_the_last_refresh_start(self):
        connector = self._make_connector()
        self._refresh_with_source(connector)
        self.assertEqual(
            connector._collection_erp_reflected_since(),
            connector.bejerman_snapshot_started_at,
        )
