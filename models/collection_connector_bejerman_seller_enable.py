# Copyright 2026 Seedian
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.fields import Command
from odoo.tools.translate import _


class CollectionConnectorBejermanSellerEnable(models.TransientModel):
    """Onboard one Bejerman seller: user, binding, phone, commission, enabled.

    Bejerman has no seller table, and the generic import only lists sellers that are
    already bound and enabled, so a new seller is enabled here instead. No Bejerman
    call is made.
    """

    _name = "collection.connector.bejerman.seller.enable"
    _description = "Enable Bejerman Seller"

    seller_id = fields.Many2one(
        comodel_name="collection.connector.bejerman.seller",
        required=True,
        readonly=True,
        ondelete="cascade",
    )
    seller_code = fields.Char(related="seller_id.seller_code")
    seller_name = fields.Char(related="seller_id.name")
    user_mode = fields.Selection(
        selection=[("existing", "Existing user"), ("new", "Create new user")],
        default="new",
        required=True,
    )
    user_id = fields.Many2one(
        comodel_name="res.users",
        string="User",
        domain="[('share', '=', False)]",
    )
    new_user_name = fields.Char(string="New user name")
    phone = fields.Char(help="Seller WhatsApp number, written on the user's partner.")
    commission_percent = fields.Float(string="Commission %", digits=(16, 2))

    @api.model
    def default_get(self, field_names):
        vals = super().default_get(field_names)
        seller = self.env["collection.connector.bejerman.seller"].browse(
            self.env.context.get("default_seller_id")
        )
        if not seller:
            return vals
        binding = seller.binding_id
        if binding:
            vals.update(
                user_mode="existing",
                user_id=binding.user_id.id,
                phone=binding.user_id.partner_id.phone or False,
                commission_percent=binding.commission_percent,
            )
        else:
            vals.update(
                user_mode="new", new_user_name=seller.name or seller.seller_code
            )
        return vals

    @api.onchange("user_id")
    def _onchange_user_id(self):
        if self.user_id and not self.phone:
            self.phone = self.user_id.partner_id.phone

    @api.private
    def _checked_phone(self, company, user):
        """Normalized phone; refuse blank or one used by another enabled seller."""
        normalize = self.env["muk_mcp.mixin"]._collection_normalize_ar_mobile
        needle = normalize(self.phone)
        if not needle:
            raise UserError(_("A seller phone is required."))
        for other in company.enabled_seller_ids - user:
            if normalize(other.phone) == needle:
                raise UserError(
                    _("The phone is already used by another enabled seller.")
                )
        return needle

    @api.private
    def _resolve_user(self, company, seller):
        """Return the user to bind, creating it first when asked to."""
        if self.user_mode == "new":
            name = (self.new_user_name or "").strip()
            if not name:
                raise UserError(_("A name is required to create the user."))
            login = company._collection_connector_seller_login(seller.seller_code)
            taken = (
                self.env["res.users"]
                .sudo()
                .with_context(active_test=False)
                .search_count([("login", "=", login)])
            )
            if taken:
                raise UserError(
                    _(
                        "A user with login %(login)s already exists. "
                        "Pick it as an existing user instead.",
                        login=login,
                    )
                )
            return None
        user = self.user_id
        if not user:
            raise UserError(_("Pick the user to enable."))
        if user.share:
            raise UserError(_("The seller must be an internal user."))
        return user

    def action_confirm(self):
        self.ensure_one()
        seller = self.seller_id
        seller._bejerman_check_manage()
        connector = seller.connector_id
        company = connector.company_id.sudo()
        if not 0 <= self.commission_percent <= 100:
            raise UserError(_("Commission percent must be between 0 and 100."))
        user = self._resolve_user(company, seller)
        self._checked_phone(company, user or self.env["res.users"])
        code = seller.seller_code
        Binding = self.env["collection.connector.seller.binding"]
        if user:
            other = Binding.search(
                [
                    ("connector_id", "=", connector.id),
                    ("user_id", "=", user.id),
                    ("external_seller_id", "!=", code),
                ],
                limit=1,
            )
            if other:
                raise UserError(
                    _(
                        "This user is already bound to seller %(code)s.",
                        code=other.external_seller_id,
                    )
                )
        else:
            user = company._collection_create_connector_seller_users(
                [
                    {
                        "external_seller_id": code,
                        "name": self.new_user_name.strip(),
                        "mobile": self.phone,
                    }
                ]
            )
        # Elevation is limited to this one user and this company, as the import does.
        if company not in user.sudo().company_ids:
            user.sudo().write({"company_ids": [Command.link(company.id)]})
        user.sudo().partner_id.write({"phone": self.phone.strip()})
        binding = Binding.search(
            [("connector_id", "=", connector.id), ("external_seller_id", "=", code)]
        )
        stale = self.env["res.users"]
        if binding:
            if binding.user_id != user:
                stale = binding.user_id
            binding.write(
                {"user_id": user.id, "commission_percent": self.commission_percent}
            )
        else:
            Binding.create(
                {
                    "connector_id": connector.id,
                    "external_seller_id": code,
                    "user_id": user.id,
                    "commission_percent": self.commission_percent,
                }
            )
        commands = [Command.link(user.id)]
        if stale:
            commands.append(Command.unlink(stale.id))
        company.write({"enabled_seller_ids": commands})
        return {"type": "ir.actions.client", "tag": "soft_reload"}
