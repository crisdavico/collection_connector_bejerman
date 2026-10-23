# Copyright 2026 Seedian
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import json
from datetime import date
from unittest.mock import MagicMock

from odoo.tests import TransactionCase

from .common import _CLIENTES


class TestBejermanMapping(TransactionCase):
    """Pure mapping of TABLAS customers and the query transport (no SOAP)."""

    def _mapping(self):
        from odoo.addons.collection_connector_bejerman.service import mapping

        return mapping

    def test_value_by_suffix_trim_and_cuit(self):
        """Suffix map, trim pad, CUIT."""
        mapping = self._mapping()
        row = {"CpoCalc_id": "000E", "CpoCalc_name": "Ana"}
        self.assertEqual(mapping.value_by_suffix(row, "id"), "000E")
        self.assertEqual(mapping.value_by_suffix(row, "missing"), None)
        self.assertEqual(mapping.trim_code("000E"), "E")
        self.assertEqual(mapping.trim_code("0"), "0")
        self.assertEqual(mapping.trim_code("000"), "0")
        self.assertEqual(mapping.canonicalize_cuit("20123456789"), "20-12345678-9")
        self.assertEqual(mapping.canonicalize_cuit("20-12345678-9"), "20-12345678-9")

    def test_debt_state_uses_today_boundary(self):
        """Overdue only when the due date is strictly before today."""
        mapping = self._mapping()
        self.assertEqual(mapping.debt_state("2026-02-14", date(2026, 2, 15)), "overdue")
        self.assertEqual(mapping.debt_state("2026-02-15", date(2026, 2, 15)), "open")
        self.assertEqual(mapping.debt_state("2026-02-16", date(2026, 2, 15)), "open")
        self.assertEqual(mapping.debt_state("", date(2026, 2, 15)), "open")

    def test_map_customer_rows_keeps_active_with_seller_code(self):
        """Customer cache rows are active-only, trimmed, canonical CUIT."""
        rows = self._mapping().map_customer_rows(_CLIENTES)
        self.assertEqual(
            rows,
            [
                {
                    "customer_code": "123",
                    "name": "Acme SA",
                    "identification": "20-12345678-9",
                    "seller_code": "E",
                },
                {
                    "customer_code": "124",
                    "name": "Other Seller Co",
                    "identification": "27-98765432-1",
                    "seller_code": "G",
                },
            ],
        )

    def test_map_customer_rows_dedupes_trimmed_codes(self):
        """Two raw codes that trim to the same code keep the first only."""
        twin = dict(_CLIENTES[0], Cliente_Codigo="123")
        rows = self._mapping().map_customer_rows([_CLIENTES[0], twin])
        self.assertEqual([row["customer_code"] for row in rows], ["123"])

    def test_find_customer_row_matches_code_and_unique_number(self):
        """CUIT still matches; a code or its unique numeric tail does too."""
        mapping = self._mapping()
        norte = {
            "Cliente_Codigo": "NS0160",
            "Cliente_RazonSocial": "Norte SA",
            "Cliente_CUIT": "30765432109",
            "Cliente_Habilitado": True,
            "Cliente_VendedorCodigo": "E",
        }
        ambiguous = dict(norte, Cliente_Codigo="AB0160", Cliente_CUIT="30111222339")
        other = dict(
            norte,
            Cliente_Codigo="ZZ0160",
            Cliente_VendedorCodigo="G",
            Cliente_CUIT="27999888776",
        )
        inactive = dict(norte, Cliente_Codigo="NS0007", Cliente_Habilitado=False)
        rows = [norte, ambiguous, other, inactive]
        for query in ("30765432109", "30-76543210-9", "NS0160", "ns0160"):
            found = mapping.find_customer_row(rows, "E", query)
            self.assertIs(found, norte, query)
        self.assertIsNone(mapping.find_customer_row(rows, "E", "0160"))
        self.assertIsNone(mapping.find_customer_row(rows, "E", "ZZ0160"))
        unique = [norte, other, inactive]
        self.assertIs(mapping.find_customer_row(unique, "E", "0160"), norte)
        self.assertIs(mapping.find_customer_row(unique, "E", "160"), norte)
        self.assertIsNone(mapping.find_customer_row(rows, "E", "0007"))

    def test_queries_decode_json_in_json(self):
        """Query views answer a JSON string holding JSON; decode it once."""
        from odoo.addons.collection_connector_bejerman.service.queries import (
            QueriesOperations,
        )

        rows = [{"a": 1}]
        for answer in (json.dumps(rows), rows):
            executor = MagicMock()
            executor.execute.return_value = answer
            self.assertEqual(
                QueriesOperations(executor).get_json_query_view("S", "V"), rows
            )

    def test_queries_reject_undecodable_string(self):
        """A string that is not JSON is a transport fault, with no payload text."""
        from odoo.addons.collection_connector_bejerman.service.errors import (
            BejermanTransportError,
        )
        from odoo.addons.collection_connector_bejerman.service.queries import (
            QueriesOperations,
        )

        executor = MagicMock()
        executor.execute.return_value = "SECRET-NOT-JSON"
        with self.assertRaises(BejermanTransportError) as ctx:
            QueriesOperations(executor).get_json_query_view("S", "V")
        self.assertNotIn("SECRET", str(ctx.exception))

    def test_get_customers_sends_empty_list_params(self):
        """The ERP refuses `{}`; ObtenerClientes takes an empty JSON list."""
        from odoo.addons.collection_connector_bejerman.service.tablas import (
            TablasOperations,
        )

        executor = MagicMock()
        TablasOperations(executor).get_customers()
        executor.execute.assert_called_once_with("TABLAS", "ObtenerClientes", [])
