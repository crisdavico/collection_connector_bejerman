# Copyright 2026 Seedian
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from unittest.mock import patch

from odoo.tests import TransactionCase

from odoo.addons.collection_connector_bejerman.service import mapping

from .common import (
    _SOAPACTION_CIERRE,
    _SOAPACTION_REGISTRO,
    BejermanTestMixin,
    _call_body,
    _call_soap_action,
    _patch_httpx,
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
    """The connector's profile reads the debt through two extension points."""

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

    def test_erp_reflected_since_is_the_last_refresh_start(self):
        connector = self._make_connector()
        self._refresh_with_source(connector)
        self.assertEqual(
            connector._collection_erp_reflected_since(),
            connector.bejerman_snapshot_started_at,
        )
