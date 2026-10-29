# Copyright 2026 Seedian
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields, models


class CollectionConnectorBejermanCustomer(models.Model):
    """Active Bejerman customer cached by the last debt snapshot refresh.

    Only enabled customers are stored, so a disabled customer reads as unknown.
    """

    _name = "collection.connector.bejerman.customer"
    _description = "Bejerman Customer Snapshot"
    _order = "customer_code"

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
    customer_code = fields.Char(required=True)
    name = fields.Char()
    identification = fields.Char()
    # The customer master's seller. Reads never scope by it: a seller sees the
    # customers their open documents name (``bejerman.debt.seller_code``).
    seller_code = fields.Char()
    # Open credit notes (negative balances) of this customer over every seller,
    # as a positive amount (decision D4). Reads net only the seller's own
    # credit-note rows.
    credit_total = fields.Float(digits=(16, 2))

    _connector_code_uniq = models.Constraint(
        "UNIQUE(connector_id, customer_code)",
        "Customer code must be unique per connector.",
    )
    _connector_identification_idx = models.Index("(connector_id, identification)")
