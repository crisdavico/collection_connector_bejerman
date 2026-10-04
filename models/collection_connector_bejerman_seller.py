# Copyright 2026 Seedian
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields, models


class CollectionConnectorBejermanSeller(models.Model):
    """Voucher seller cached by the last debt snapshot refresh.

    Bejerman has no seller view, so sellers come from the voucher seller carried by
    every row of the debt view. Commission, phone and enabled state are not stored
    here: they live in Odoo and are merged back when the seller list is read.
    """

    _name = "collection.connector.bejerman.seller"
    _description = "Bejerman Seller Snapshot"
    _order = "seller_code"

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
    seller_code = fields.Char(required=True)
    name = fields.Char()

    _connector_code_uniq = models.Constraint(
        "UNIQUE(connector_id, seller_code)",
        "Seller code must be unique per connector.",
    )
