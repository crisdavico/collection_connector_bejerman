# Copyright 2026 Seedian
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from lxml import etree

from odoo.tests import TransactionCase

from .common import BejermanTestMixin

_MANAGER = "collection.group_collection_manager"
_USER = "collection.group_collection_user"


class TestBejermanDebtViews(BejermanTestMixin, TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.menu = cls.env.ref("collection_connector_bejerman.menu_bejerman_debt")
        cls.action = cls.env.ref("collection_connector_bejerman.action_bejerman_debt")

    def _snapshot(self):
        connector = self._make_connector()
        connector._bejerman_replace_snapshot(
            customers=[
                {"customer_code": "C1", "name": "Acme SA"},
                {"customer_code": "C2", "name": "Globex SRL"},
            ],
            debts=[
                {"external_invoice_id": "1", "customer_code": "C1", "balance": 100},
                {"external_invoice_id": "2", "customer_code": "C2", "balance": 50},
                {"external_invoice_id": "3", "customer_code": "C9", "balance": 10},
            ],
            sellers=[],
        )
        return self.env["collection.connector.bejerman.debt"].search(
            [("connector_id", "=", connector.id)]
        )

    def test_menu_visible_only_to_managers(self):
        manager = self._create_user("debt_manager", _MANAGER)
        user = self._create_user("debt_user", _USER)
        self.assertEqual(self.menu.group_ids, self.env.ref(_MANAGER))
        self.assertEqual(
            self.menu.parent_id, self.env.ref("collection.menu_collection_root")
        )
        self.assertEqual(self.menu.action, self.action)
        self.assertTrue(self.menu.group_ids & manager.all_group_ids)
        self.assertFalse(self.menu.group_ids & user.all_group_ids)

    def test_list_is_read_only_and_shows_debt(self):
        manager = self._create_user("debt_manager", _MANAGER)
        self.assertEqual(self.action.res_model, "collection.connector.bejerman.debt")
        views = (
            self.env["collection.connector.bejerman.debt"]
            .with_user(manager)
            .get_views([(False, "list"), (False, "search")])
        )
        arch = etree.fromstring(views["views"]["list"]["arch"])
        for attr in ("create", "edit", "delete"):
            self.assertEqual(arch.get(attr), "false")
        names = arch.xpath("//field/@name")
        for name in ("customer_code", "customer_name", "number", "balance"):
            self.assertIn(name, names)

    def test_customer_name_comes_from_customer_snapshot(self):
        debts = self._snapshot()
        by_invoice = {d.external_invoice_id: d.customer_name for d in debts}
        self.assertEqual(by_invoice, {"1": "Acme SA", "2": "Globex SRL", "3": False})

    def test_search_by_customer_name(self):
        debts = self._snapshot()
        found = debts.search(
            [("id", "in", debts.ids), ("customer_name", "ilike", "acme")]
        )
        self.assertEqual(found.mapped("external_invoice_id"), ["1"])
