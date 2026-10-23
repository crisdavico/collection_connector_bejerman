# Copyright 2026 Seedian
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError
from odoo.fields import Command
from odoo.tools.translate import _

_MANAGE_GROUPS = ("base.group_system", "collection.group_collection_manager")


class CollectionConnectorBejermanSeller(models.Model):
    """Voucher seller cached by the last debt snapshot refresh.

    Bejerman has no seller view, so the connector's profile reads the sellers from
    its debt source (the voucher sellers of the debt view, say). Commission, phone
    and enabled state are not stored here: they live in Odoo (binding, user,
    company) and are shown and changed through the **Enable seller** / **Disable
    seller** actions.
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
    binding_id = fields.Many2one(
        comodel_name="collection.connector.seller.binding",
        compute="_compute_odoo_values",
        string="Binding",
    )
    user_id = fields.Many2one(
        comodel_name="res.users",
        compute="_compute_odoo_values",
        string="Odoo User",
    )
    commission_percent = fields.Float(
        compute="_compute_odoo_values", digits=(16, 2), string="Commission %"
    )
    is_enabled = fields.Boolean(compute="_compute_odoo_values", string="Enabled")

    _connector_code_uniq = models.Constraint(
        "UNIQUE(connector_id, seller_code)",
        "Seller code must be unique per connector.",
    )

    @api.depends(
        "connector_id.seller_binding_ids.external_seller_id",
        "connector_id.seller_binding_ids.user_id",
        "connector_id.seller_binding_ids.commission_percent",
        "connector_id.company_id.enabled_seller_ids",
    )
    def _compute_odoo_values(self):
        for seller in self:
            binding = seller.connector_id.seller_binding_ids.filtered(
                lambda b, code=seller.seller_code: b.external_seller_id == code
            )[:1]
            seller.binding_id = binding
            seller.user_id = binding.user_id
            seller.commission_percent = binding.commission_percent if binding else 0.0
            seller.is_enabled = bool(binding) and (
                binding.user_id in seller.connector_id.company_id.enabled_seller_ids
            )

    @api.private
    def _bejerman_check_manage(self):
        """Only administrators and collections managers, on Bejerman connectors."""
        user = self.env.user
        if not any(user.has_group(group) for group in _MANAGE_GROUPS):
            raise AccessError(
                _("Only administrators and Collections Managers can do this.")
            )
        for seller in self:
            if seller.connector_id.type != "bejerman":
                raise UserError(
                    _("The requested connector operation is not available.")
                )

    def action_bejerman_enable_seller(self):
        """Open the wizard that binds, equips and enables this seller."""
        self.ensure_one()
        self._bejerman_check_manage()
        return {
            "type": "ir.actions.act_window",
            "name": _("Enable seller"),
            "res_model": "collection.connector.bejerman.seller.enable",
            "view_mode": "form",
            "target": "new",
            "context": {"default_seller_id": self.id},
        }

    def action_bejerman_disable_seller(self):
        """Take the seller out of the enabled sellers; the binding is kept."""
        self.ensure_one()
        self._bejerman_check_manage()
        if not self.is_enabled:
            raise UserError(_("This seller is not enabled."))
        # Elevation is limited to removing one bound user from this company.
        self.connector_id.company_id.sudo().write(
            {"enabled_seller_ids": [Command.unlink(self.user_id.id)]}
        )
        return {"type": "ir.actions.client", "tag": "soft_reload"}
