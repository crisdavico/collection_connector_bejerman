# Copyright 2026 Seedian
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError
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
    company_id = fields.Many2one(related="seller_id.company_id")
    user_mode = fields.Selection(
        selection=[("existing", "Existing user"), ("new", "Create new user")],
        default="new",
        required=True,
    )
    # Only users already in the company: enabling never widens company access.
    user_id = fields.Many2one(
        comodel_name="res.users",
        string="User",
        domain="[('share', '=', False), ('company_ids', 'in', company_id)]",
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
        if company not in user.sudo().company_ids:
            raise UserError(
                _(
                    "%(user)s does not belong to %(company)s. An administrator must "
                    "give the user access to the company before it can be enabled.",
                    user=user.display_name,
                    company=company.display_name,
                )
            )
        return user

    @api.private
    def _write_seller_phone(self, user):
        """Set the user's contact phone as the current user, never with sudo.

        A matching phone is left alone. Another user's contact is usually not
        the manager's to edit; the refusal names who can do it.
        """
        normalize = self.env["muk_mcp.mixin"]._collection_normalize_ar_mobile
        partner = user.partner_id
        if normalize(partner.phone) == normalize(self.phone):
            return
        try:
            with self.env.cr.savepoint():
                partner.write({"phone": self.phone.strip()})
        except AccessError:
            raise UserError(
                _(
                    "You cannot change the phone of %(user)s. An administrator must "
                    "set it on the user's contact, then enable the seller again.",
                    user=user.display_name,
                )
            ) from None

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
            # First write: a refusal leaves no binding and no enabled seller.
            self._write_seller_phone(user)
        else:
            # A new seller identity is created in this company only, with the
            # phone, as the import does.
            user = company._collection_create_connector_seller_users(
                [
                    {
                        "external_seller_id": code,
                        "name": self.new_user_name.strip(),
                        "mobile": self.phone.strip(),
                    }
                ]
            )
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
