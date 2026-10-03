# Copyright 2026 Seedian
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import logging

import pytz

from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError
from odoo.tools.translate import _

from ..service import mapping
from ..service.errors import BejermanError
from ..service.session import BejermanClient
from ..service.settings import Credentials, Settings

_logger = logging.getLogger(__name__)

DEFAULT_QUOTATION_KINDS = "PRE"


def _customer_payload(customer):
    """Sqlite-raw customer row for ``collection.connector._format_*``."""
    return {
        "id": customer.customer_code,
        "name": customer.name or "",
        "identification": customer.identification or "",
        "customer_code": customer.customer_code,
        "active": True,
    }


def _invoice_payload(debt, today):
    """Sqlite-raw invoice row; ``state`` depends on today, so it is never stored."""
    due_date = debt.due_date.isoformat() if debt.due_date else ""
    return {
        "id": debt.external_invoice_id,
        "number": debt.number or "",
        "issue_date": debt.issue_date.isoformat() if debt.issue_date else "",
        "due_date": due_date,
        "amount": debt.amount,
        "balance": debt.balance,
        "state": mapping.debt_state(due_date, today),
        "document_kind": debt.document_kind,
    }


class CollectionConnectorBejerman(models.Model):
    _inherit = "collection.connector"

    type = fields.Selection(
        selection_add=[("bejerman", "Bejerman")],
        ondelete={"bejerman": "cascade"},
    )
    bejerman_ws_url = fields.Char(
        string="Bejerman WS URL",
        groups="base.group_system",
    )
    bejerman_usuario = fields.Char(
        string="Bejerman User",
        groups="base.group_system",
    )
    bejerman_clave = fields.Char(
        string="Bejerman Password",
        groups="base.group_system",
    )
    bejerman_empresa = fields.Char(
        string="Bejerman Company",
        groups="base.group_system",
    )
    bejerman_puesto = fields.Char(
        string="Bejerman Workstation",
        groups="base.group_system",
    )
    bejerman_sucursal = fields.Char(
        string="Bejerman Branch",
        groups="base.group_system",
    )
    bejerman_timeout = fields.Integer(
        default=60,
        groups="base.group_system",
    )
    bejerman_allow_insecure = fields.Boolean(
        string="Allow Insecure Bejerman HTTP/TLS",
        groups="base.group_system",
    )
    bejerman_ca_bundle = fields.Char(
        string="Bejerman CA Bundle",
        groups="base.group_system",
    )
    bejerman_seller_scenario = fields.Char(
        groups="base.group_system",
    )
    bejerman_seller_view = fields.Char(
        groups="base.group_system",
    )
    bejerman_debt_scenario = fields.Char(
        groups="base.group_system",
    )
    bejerman_debt_view = fields.Char(
        groups="base.group_system",
    )
    bejerman_quotation_kinds = fields.Char(
        default=DEFAULT_QUOTATION_KINDS,
        groups="base.group_system",
    )
    bejerman_debt_filter_field = fields.Char(
        help="Query-view column (e.g. CVE_CODCLI) that filters the debt view by "
        "customer. When set, debt is read live per customer instead of from the "
        "snapshot.",
        groups="base.group_system",
    )
    # Snapshot bookkeeping is not sensitive and must stay readable by internal
    # users: the read path checks `bejerman_snapshot_refreshed_at` for emptiness.
    bejerman_snapshot_refreshed_at = fields.Datetime(readonly=True, copy=False)
    bejerman_snapshot_customer_count = fields.Integer(readonly=True, copy=False)
    bejerman_snapshot_debt_count = fields.Integer(readonly=True, copy=False)

    @api.private
    def _bejerman_quotation_kinds(self):
        """Configured quotation voucher types; blank means the default ``PRE``."""
        self.ensure_one()
        return self.bejerman_quotation_kinds or DEFAULT_QUOTATION_KINDS

    @api.private
    def _bejerman_today(self):
        """Today's date in the company timezone (partner tz, else user, else UTC)."""
        self.ensure_one()
        tz_name = self.company_id.partner_id.tz or self.env.user.tz or "UTC"
        try:
            tz = pytz.timezone(tz_name)
        except pytz.UnknownTimeZoneError:
            tz = pytz.utc
        return pytz.utc.localize(fields.Datetime.now()).astimezone(tz).date()

    @api.private
    def _bejerman_misconfigured(self):
        raise UserError(_("The collection connector is not configured."))

    @api.private
    def _bejerman_settings(self):
        self.ensure_one()
        try:
            return Settings(
                ws_url=self.bejerman_ws_url or "",
                credentials=Credentials(
                    usuario=self.bejerman_usuario or "",
                    clave=self.bejerman_clave or "",
                    empresa=self.bejerman_empresa or "",
                    puesto=self.bejerman_puesto or "",
                    sucursal=self.bejerman_sucursal or "",
                ),
                timeout=float(self.bejerman_timeout or 60),
                allow_insecure=bool(self.bejerman_allow_insecure),
                ca_bundle=self.bejerman_ca_bundle or "",
            )
        except BejermanError:
            self._bejerman_misconfigured()

    @api.private
    def _bejerman_client(self):
        return BejermanClient(self._bejerman_settings())

    @api.private
    def _bejerman_call(self, operation):
        try:
            with self._bejerman_client() as client:
                return operation(client)
        except (BejermanError, TypeError, ValueError):
            self._bejerman_misconfigured()

    @api.private
    def _bejerman_test_connection(self):
        self.ensure_one()

        # The debt view is a ~200 MB download: only the snapshot refresh reads it.
        def _probe(client):
            client.tablas.obtener_clientes()
            client.queries.obtener_json_query_vista(
                self.bejerman_seller_scenario or "",
                self.bejerman_seller_view or "",
            )
            return True

        return self._bejerman_call(_probe)

    @api.private
    def _bejerman_refresh_failed(self, exc):
        """Log the failure class only (never its text) and raise a generic error."""
        _logger.warning(
            "Bejerman debt snapshot refresh failed for connector %s: %s",
            self.id,
            type(exc).__name__,
        )
        raise UserError(
            _(
                "The Bejerman debt snapshot could not be refreshed. "
                "The previous snapshot was kept."
            )
        ) from None

    @api.private
    def _bejerman_refresh_snapshot(self):
        """Download customers and open debt, then replace this connector's snapshot.

        The ERP is read first, inside one Registro -> Cierre session, and nothing is
        written until both answers mapped cleanly; the swap itself is one savepoint.
        Any failure keeps the previous snapshot.
        """
        self.ensure_one()
        kinds = self._bejerman_quotation_kinds()
        scenario = self.bejerman_debt_scenario or ""
        view = self.bejerman_debt_view or ""
        try:
            with self._bejerman_client() as client:
                customers = mapping.map_customer_rows(client.tablas.obtener_clientes())
                # Debt of disabled or unknown customers is not brought.
                debts = mapping.map_open_debt(
                    client.queries.obtener_json_query_vista(scenario, view),
                    kinds,
                    customer_codes={row["customer_code"] for row in customers},
                )
        except (BejermanError, TypeError, ValueError) as exc:
            self._bejerman_refresh_failed(exc)
        self._bejerman_replace_snapshot(customers, debts)
        return True

    @api.model
    @api.private
    def _bejerman_cron_refresh_snapshot(self):
        """Refresh every active Bejerman connector; one failure stops no other."""
        for connector in self.search([("type", "=", "bejerman")]):
            try:
                with self.env.cr.savepoint():
                    connector._bejerman_refresh_snapshot()
            except Exception as exc:
                _logger.warning(
                    "Bejerman debt snapshot cron failed for connector %s: %s",
                    connector.id,
                    type(exc).__name__,
                )

    def action_bejerman_refresh_snapshot(self):
        """Admin button: refresh this connector's debt snapshot now."""
        self.ensure_one()
        if not self.env.user._is_system():
            raise AccessError(
                _("Only administrators can refresh the Bejerman debt snapshot.")
            )
        if self.type != "bejerman":
            raise UserError(_("The requested connector operation is not available."))
        self._bejerman_refresh_snapshot()
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "type": "success",
                "title": _("Debt Snapshot Refreshed"),
                "message": _(
                    "%(debts)s open vouchers and %(customers)s customers loaded.",
                    debts=self.bejerman_snapshot_debt_count,
                    customers=self.bejerman_snapshot_customer_count,
                ),
                "sticky": False,
            },
        }

    @api.private
    def _bejerman_replace_snapshot(self, customers, debts):
        self.ensure_one()
        Customer = self.env["collection.connector.bejerman.customer"]
        Debt = self.env["collection.connector.bejerman.debt"]
        scope = [("connector_id", "=", self.id)]
        try:
            with self.env.cr.savepoint():
                Customer.search(scope).unlink()
                Debt.search(scope).unlink()
                Customer.create([dict(row, connector_id=self.id) for row in customers])
                Debt.create([dict(row, connector_id=self.id) for row in debts])
                self.write(
                    {
                        "bejerman_snapshot_refreshed_at": fields.Datetime.now(),
                        "bejerman_snapshot_customer_count": len(customers),
                        "bejerman_snapshot_debt_count": len(debts),
                    }
                )
        except Exception as exc:
            self._bejerman_refresh_failed(exc)

    @api.private
    def _bejerman_list_sellers(self):
        self.ensure_one()

        def _list_sellers(client):
            rows = client.queries.obtener_json_query_vista(
                self.bejerman_seller_scenario or "",
                self.bejerman_seller_view or "",
            )
            return mapping.map_sellers(rows)

        return self._bejerman_call(_list_sellers)

    @api.private
    def _bejerman_require_snapshot(self):
        """Fail closed before the first refresh instead of downloading inline."""
        self.ensure_one()
        if not self.bejerman_snapshot_refreshed_at:
            self._bejerman_misconfigured()

    @api.private
    def _bejerman_list_customers(self, external_seller_id):
        self.ensure_one()
        self._bejerman_require_snapshot()
        customers = self.env["collection.connector.bejerman.customer"].search(
            [
                ("connector_id", "=", self.id),
                ("seller_code", "=", mapping.trim_code(external_seller_id)),
            ]
        )
        return [_customer_payload(customer) for customer in customers]

    @api.private
    def _bejerman_get_customer_debt(self, external_seller_id, customer_identification):
        self.ensure_one()
        # Config flag read with sudo: it only picks the code path, nothing is returned.
        if self.sudo().bejerman_debt_filter_field:
            return self.sudo()._bejerman_live_customer_debt(
                external_seller_id, customer_identification
            )
        self._bejerman_require_snapshot()
        customers = self.env["collection.connector.bejerman.customer"].search(
            [
                ("connector_id", "=", self.id),
                ("seller_code", "=", mapping.trim_code(external_seller_id)),
                (
                    "identification",
                    "=",
                    mapping.canonicalize_cuit(customer_identification),
                ),
            ]
        )
        if len(customers) != 1:
            return {"customer": None, "invoices": []}
        debts = self.env["collection.connector.bejerman.debt"].search(
            [
                ("connector_id", "=", self.id),
                ("customer_code", "=", customers.customer_code),
            ],
            order="due_date, number, external_invoice_id",
        )
        today = self._bejerman_today()
        return {
            "customer": _customer_payload(customers),
            "invoices": [_invoice_payload(debt, today) for debt in debts],
        }

    @api.private
    def _bejerman_live_customer_debt(self, external_seller_id, customer_identification):
        """Read one customer's open debt live from the debt view, filtered.

        Used only when ``bejerman_debt_filter_field`` is set, i.e. the ERP view can
        filter server side. Runs on a sudo record: credentials stay admin-only.
        """
        self.ensure_one()
        field = self.bejerman_debt_filter_field

        def _get_debt(client):
            row = mapping.find_customer_row(
                client.tablas.obtener_clientes(),
                external_seller_id,
                customer_identification,
            )
            if row is None:
                return {"customer": None, "invoices": []}
            customer = mapping.customer_from_row(row)
            rows = client.queries.obtener_json_query_vista(
                self.bejerman_debt_scenario or "",
                self.bejerman_debt_view or "",
                mapping.debt_filter(field, mapping.erp_customer_code(row)),
            )
            today = self._bejerman_today()
            entries = mapping.map_open_debt(
                rows,
                self._bejerman_quotation_kinds(),
                customer_code=customer["customer_code"],
            )
            return {
                "customer": customer,
                "invoices": [mapping.entry_to_invoice(e, today) for e in entries],
            }

        return self._bejerman_call(_get_debt)
