# Copyright 2026 Seedian
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from collections import defaultdict

from odoo import api, fields, models
from odoo.fields import Domain


class CollectionConnectorBejermanDebt(models.Model):
    """One open sales voucher of the last Bejerman debt snapshot.

    Rows are replaced wholesale by ``collection.connector._bejerman_refresh_snapshot``.
    ``state`` is deliberately not stored: it depends on today's date.
    """

    _name = "collection.connector.bejerman.debt"
    _description = "Bejerman Open Debt Snapshot"
    _order = "customer_code, due_date, external_invoice_id"

    connector_id = fields.Many2one(
        comodel_name="collection.connector",
        required=True,
        ondelete="cascade",
    )
    company_id = fields.Many2one(
        related="connector_id.company_id",
        store=True,
        required=True,
        precompute=True,
        index=True,
    )
    external_invoice_id = fields.Char(required=True)
    number = fields.Char()
    customer_code = fields.Char(required=True)
    # Read from the customer snapshot of the same refresh; False when the
    # customer row is missing.
    customer_name = fields.Char(
        compute="_compute_customer_name",
        search="_search_customer_name",
    )
    seller_code = fields.Char()
    issue_date = fields.Date()
    due_date = fields.Date()
    amount = fields.Float(digits=(16, 2))
    balance = fields.Float(digits=(16, 2))
    document_kind = fields.Selection(
        selection=[("invoice", "Invoice"), ("quotation", "Quotation")],
        required=True,
        default="invoice",
    )

    _connector_invoice_uniq = models.Constraint(
        "UNIQUE(connector_id, external_invoice_id)",
        "External invoice id must be unique per connector.",
    )
    _connector_customer_idx = models.Index("(connector_id, customer_code)")

    @api.depends("connector_id", "customer_code")
    def _compute_customer_name(self):
        customers = self.env["collection.connector.bejerman.customer"].search(
            [
                ("connector_id", "in", self.connector_id.ids),
                ("customer_code", "in", self.mapped("customer_code")),
            ]
        )
        names = {(c.connector_id.id, c.customer_code): c.name for c in customers}
        for debt in self:
            debt.customer_name = names.get(
                (debt.connector_id.id, debt.customer_code), False
            )

    def _search_customer_name(self, operator, value):
        customers = self.env["collection.connector.bejerman.customer"].search(
            [("name", operator, value)]
        )
        codes_by_connector = defaultdict(list)
        for customer in customers:
            codes_by_connector[customer.connector_id.id].append(customer.customer_code)
        return Domain.OR(
            Domain("connector_id", "=", connector_id)
            & Domain("customer_code", "in", codes)
            for connector_id, codes in codes_by_connector.items()
        )
