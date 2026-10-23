# Copyright 2026 Seedian
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields, models


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
    seller_code = fields.Char()
    issue_date = fields.Date()
    due_date = fields.Date()
    amount = fields.Float(digits=(16, 2))
    balance = fields.Float(digits=(16, 2))
    # Untaxed share (NETO + NGEX) of amount and balance, from the sales VAT book
    # view; equal to them for quotations and invoices that view does not list.
    amount_untaxed = fields.Float(digits=(16, 2))
    balance_untaxed = fields.Float(digits=(16, 2))
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
