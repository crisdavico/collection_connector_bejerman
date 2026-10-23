# Copyright 2026 Seedian
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import logging
from datetime import timedelta
from urllib.parse import urlparse

import pytz
from markupsafe import Markup

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools.translate import _

from odoo.addons.collection.models.collection_common import (
    COLLECTION_MANAGER_GROUP,
    ConnectorDataStaleError,
    is_privileged,
    privileged,
)

from ..service import mapping
from ..service.errors import (
    BejermanConfigError,
    BejermanDeadlineError,
    BejermanError,
    BejermanTransportError,
)
from ..service.session import BejermanClient
from ..service.settings import Credentials, Settings

_logger = logging.getLogger(__name__)

DEFAULT_SNAPSHOT_MAX_AGE_HOURS = 24
DEFAULT_DEADLINE_SECONDS = 900
SYNC_FAILED_ACTIVITY = (
    "collection_connector_bejerman.mail_activity_type_bejerman_sync_failed"
)
# Snapshot bookkeeping is written only by the refresh itself, so nobody can make
# a stale snapshot look fresh (or hide a failure) with a plain write.
SNAPSHOT_SCOPE = "collection_connector_bejerman_snapshot"
_SNAPSHOT_FIELDS = frozenset(
    {
        "bejerman_snapshot_started_at",
        "bejerman_snapshot_refreshed_at",
        "bejerman_snapshot_customer_count",
        "bejerman_snapshot_debt_count",
        "bejerman_snapshot_skipped_count",
        "bejerman_last_failure_at",
        "bejerman_last_failure_reason",
        "bejerman_failure_count",
    }
)
# Generic failure classes: what an operator can act on, never the ERP's text.
FAILURE_REASONS = [
    ("connection", "Could not reach the Bejerman server"),
    ("timeout", "The Bejerman server took too long"),
    ("erp", "Bejerman refused the request"),
    ("configuration", "The connector is not configured"),
    ("data", "The Bejerman answer could not be read"),
    ("storage", "The snapshot could not be stored"),
    ("other", "Unexpected error"),
]
# Settings the SOAP session cannot start without (the branch is optional).
_REQUIRED_SETTINGS = (
    "bejerman_ws_url",
    "bejerman_usuario",
    "bejerman_clave",
    "bejerman_empresa",
    "bejerman_puesto",
)


def _customer_payload(customer):
    """Sqlite-raw customer row for ``collection.connector._format_*``."""
    return {
        "id": customer.customer_code,
        "name": customer.name or "",
        "identification": customer.identification or "",
        "customer_code": customer.customer_code,
        "active": True,
    }


def failure_reason(exc):
    """Generic failure class of a refresh exception (never its text)."""
    reason = getattr(exc, "bejerman_reason", None)
    if reason:
        return reason
    if isinstance(exc, BejermanDeadlineError):
        return "timeout"
    if isinstance(exc, BejermanTransportError):
        return "connection"
    if isinstance(exc, BejermanConfigError):
        return "configuration"
    if isinstance(exc, BejermanError):
        return "erp"
    if isinstance(exc, (TypeError, ValueError)):
        return "data"
    if isinstance(exc, UserError):
        return "configuration"
    return "other"


class CollectionConnectorBejerman(models.Model):
    _name = "collection.connector"
    _inherit = ["collection.connector", "mail.thread", "mail.activity.mixin"]

    type = fields.Selection(
        selection_add=[("bejerman", "Bejerman")],
        ondelete={"bejerman": "cascade"},
    )
    # Several customers' connectors share one database: the profile picks, per
    # connector, which addon reads its debt. Customer addons add their value.
    bejerman_profile = fields.Selection(
        selection=[("standard", "Standard")],
        default="standard",
        required=True,
        help="Which customer-specific addon reads this connector's debt. "
        "Standard reads customers only and has no debt source.",
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
        groups="base.group_system,collection.group_collection_manager",
    )
    bejerman_puesto = fields.Char(
        string="Bejerman Workstation",
        groups="base.group_system,collection.group_collection_manager",
    )
    bejerman_sucursal = fields.Char(
        string="Bejerman Branch",
        groups="base.group_system,collection.group_collection_manager",
    )
    bejerman_timeout = fields.Integer(
        default=60,
        groups="base.group_system,collection.group_collection_manager",
    )
    bejerman_deadline = fields.Integer(
        string="Bejerman Deadline (s)",
        default=DEFAULT_DEADLINE_SECONDS,
        help="Wall-clock limit of one Bejerman session (login, reads, retries "
        "and close). A download still running past it is aborted.",
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
    # Snapshot bookkeeping is not sensitive and must stay readable by internal
    # users: the read path checks `bejerman_snapshot_refreshed_at` for its age.
    bejerman_seller_ids = fields.One2many(
        comodel_name="collection.connector.bejerman.seller",
        inverse_name="connector_id",
        string="Bejerman Sellers",
        readonly=True,
        copy=False,
    )
    bejerman_snapshot_started_at = fields.Datetime(
        string="Last Refresh Started",
        readonly=True,
        copy=False,
        help="When the last successful refresh started reading Bejerman.",
    )
    bejerman_snapshot_refreshed_at = fields.Datetime(
        string="Last Refresh", readonly=True, copy=False
    )
    bejerman_snapshot_customer_count = fields.Integer(readonly=True, copy=False)
    bejerman_snapshot_debt_count = fields.Integer(readonly=True, copy=False)
    bejerman_snapshot_skipped_count = fields.Integer(
        string="Rows Skipped (unreadable amount)",
        readonly=True,
        copy=False,
        help="Debt rows of the last refresh left out because their balance or "
        "amount could not be read. They are never counted as zero.",
    )
    bejerman_last_failure_at = fields.Datetime(
        string="Last Failure", readonly=True, copy=False
    )
    bejerman_last_failure_reason = fields.Selection(
        selection=FAILURE_REASONS,
        string="Last Failure Reason",
        readonly=True,
        copy=False,
    )
    bejerman_failure_count = fields.Integer(
        string="Failures Since Last Refresh",
        readonly=True,
        copy=False,
        help="Scheduled refreshes that failed since the last successful one.",
    )
    bejerman_snapshot_max_age_hours = fields.Integer(
        string="Maximum Debt Age (hours)",
        default=DEFAULT_SNAPSHOT_MAX_AGE_HOURS,
        help="Debt read from a snapshot older than this is refused to sellers "
        "and operators instead of being shown.",
    )

    @api.constrains("bejerman_snapshot_max_age_hours")
    def _check_bejerman_snapshot_max_age_hours(self):
        for connector in self:
            if connector.bejerman_snapshot_max_age_hours < 1:
                raise ValidationError(
                    _("The maximum debt age must be at least one hour.")
                )

    @api.model_create_multi
    def create(self, vals_list):
        if not is_privileged(SNAPSHOT_SCOPE) and any(
            _SNAPSHOT_FIELDS & set(vals) for vals in vals_list
        ):
            self._bejerman_raise_snapshot_status_locked()
        return super().create(vals_list)

    def write(self, vals):
        if _SNAPSHOT_FIELDS & set(vals) and not is_privileged(SNAPSHOT_SCOPE):
            self._bejerman_raise_snapshot_status_locked()
        return super().write(vals)

    @api.model
    @api.private
    def _bejerman_raise_snapshot_status_locked(self):
        raise UserError(_("The Bejerman snapshot status is only updated by a refresh."))

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
    def _bejerman_build_settings(self):
        """Build ``Settings`` from the fields; raises ``BejermanConfigError``."""
        self.ensure_one()
        return Settings(
            ws_url=self.bejerman_ws_url or "",
            credentials=Credentials(
                user=self.bejerman_usuario or "",
                password=self.bejerman_clave or "",
                company=self.bejerman_empresa or "",
                workstation=self.bejerman_puesto or "",
                branch=self.bejerman_sucursal or "",
            ),
            timeout=float(self.bejerman_timeout or 60),
            allow_insecure=bool(self.bejerman_allow_insecure),
            ca_bundle=self.bejerman_ca_bundle or "",
            deadline=float(self.bejerman_deadline or DEFAULT_DEADLINE_SECONDS),
        )

    @api.private
    def _bejerman_settings(self):
        self.ensure_one()
        try:
            return self._bejerman_build_settings()
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
    def _bejerman_test_settings(self):
        """Settings for Test Connection; failures name the setting, not its value."""
        missing = [
            self._fields[name].string
            for name in _REQUIRED_SETTINGS
            if not (self[name] or "").strip()
        ]
        if missing:
            raise UserError(
                _(
                    "The Bejerman connector is not configured. "
                    "Missing settings: %(settings)s.",
                    settings=", ".join(missing),
                )
            )
        try:
            return self._bejerman_build_settings()
        except BejermanConfigError as exc:
            # Config errors carry fixed texts that never quote a value.
            raise UserError(
                _("The Bejerman settings are not valid: %(reason)s.", reason=str(exc))
            ) from None

    @api.private
    def _bejerman_test_failed(self, stage, exc, host):
        """Log the failure class only, then raise the message for the failed stage."""
        _logger.warning(
            "Bejerman test connection failed for connector %s at %s: %s",
            self.id,
            stage,
            type(exc).__name__,
        )
        if isinstance(exc, BejermanTransportError):
            message = _(
                "Could not reach the Bejerman server at %(host)s. "
                "Check the WS URL, the network connection and the certificate "
                "settings.",
                host=host,
            )
        elif stage == "login":
            message = _(
                "Bejerman rejected the login. "
                "Check the user, password, company and workstation."
            )
        elif stage == "customers":
            message = _(
                "Connected to Bejerman, but the customer list could not be read."
            )
        else:
            message = _("Bejerman answered, but the session could not be closed.")
        raise UserError(message) from None

    @api.private
    def _bejerman_test_connection(self):
        self.ensure_one()
        settings = self._bejerman_test_settings()
        host = urlparse(settings.ws_url).hostname
        stage = "login"
        # Bejerman has no seller view, and debt views are large downloads that only
        # the snapshot refresh reads: Test Connection is login plus customers.
        try:
            with BejermanClient(settings) as client:
                stage = "customers"
                client.tablas.get_customers()
                stage = "close"
        except (BejermanError, TypeError, ValueError) as exc:
            self._bejerman_test_failed(stage, exc, host)
        return True

    @api.private
    def _bejerman_refresh_failed(self, exc, reason=None):
        """Log the failure class only (never its text) and raise a generic error.

        The raised error carries the generic reason class for the cron's record.
        """
        _logger.warning(
            "Bejerman debt snapshot refresh failed for connector %s: %s",
            self.id,
            type(exc).__name__,
        )
        error = UserError(
            _(
                "The Bejerman debt snapshot could not be refreshed. "
                "The previous snapshot was kept."
            )
        )
        error.bejerman_reason = reason or failure_reason(exc)
        raise error from None

    @api.private
    def _bejerman_raise_no_debt_source(self):
        """Always raises: the standard profile has no debt source."""
        raise UserError(
            _(
                "The Bejerman connector has no debt source. "
                "Choose the Bejerman profile of its customer."
            )
        )

    @api.private
    def _bejerman_check_snapshot_source(self):
        """Fail before opening a session when the profile cannot read debt.

        Profile addons override it to check their own settings; the standard
        profile has no debt source, so its refresh fails as a configuration error.
        """
        self.ensure_one()
        self._bejerman_raise_no_debt_source()

    @api.private
    def _bejerman_read_snapshot(self, client, today, stats):
        """Read ``(customers, debts, sellers)`` inside the open Bejerman session.

        The standard profile has no debt source, so this base version always
        raises; profile addons override it and return what follows. Customers
        are ``mapping.map_customer_rows``
        rows, optionally with ``credit_total``; debts and sellers are the field
        values of the debt and seller snapshot rows. Rows skipped because an
        amount could not be read are counted in ``stats["unparsable_amounts"]``.
        """
        self.ensure_one()
        self._bejerman_raise_no_debt_source()

    @api.private
    def _bejerman_refresh_snapshot(self):
        """Read the profile's snapshot, then replace this connector's snapshot.

        The ERP is read first, inside one Registro -> Cierre session, and nothing is
        written until every answer mapped cleanly; the swap itself is one savepoint.
        Any failure keeps the previous snapshot.
        """
        self.ensure_one()
        self._bejerman_check_snapshot_source()
        started_at = fields.Datetime.now()
        stats = {}
        today = self._bejerman_today()
        try:
            with self._bejerman_client() as client:
                customers, debts, sellers = self._bejerman_read_snapshot(
                    client, today, stats
                )
        except (BejermanError, TypeError, ValueError) as exc:
            self._bejerman_refresh_failed(exc)
        skipped = self._bejerman_log_skipped_rows(stats)
        self._bejerman_log_snapshot_read(stats, today)
        self._bejerman_replace_snapshot(
            customers, debts, sellers, started_at, skipped=skipped
        )
        self._bejerman_clear_sync_notices()
        return True

    @api.private
    def _bejerman_log_snapshot_read(self, stats, today):
        """Profiles log what their read left out, once the session is closed."""
        self.ensure_one()

    @api.private
    def _bejerman_log_skipped_rows(self, stats):
        """Log (count only, no values) the rows skipped for an unreadable amount."""
        skipped = stats.get("unparsable_amounts", 0)
        if skipped:
            _logger.warning(
                "Bejerman debt of connector %s: %s rows skipped, their balance or "
                "amount could not be read",
                self.id,
                skipped,
            )
        return skipped

    @api.model
    @api.private
    def _bejerman_cron_refresh_snapshot(self):
        """Refresh every active Bejerman connector; one failure stops no other.

        A failure is recorded on its connector (time and generic reason) and the
        company's Collections Managers get one notice until the next success.
        The cron itself does not fail: that would roll the record back and,
        after repeated failures, deactivate the cron.
        """
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
                try:
                    with self.env.cr.savepoint():
                        connector._bejerman_record_sync_failure(failure_reason(exc))
                except Exception as record_exc:
                    _logger.warning(
                        "Bejerman sync failure of connector %s could not be "
                        "recorded: %s",
                        connector.id,
                        type(record_exc).__name__,
                    )

    @api.private
    def _bejerman_record_sync_failure(self, reason):
        """Store the failure and notify the managers once per outage.

        The notice is best effort: one that cannot be posted (its activity type
        deleted, say) is logged by class and never undoes the record.
        """
        self.ensure_one()
        with privileged(SNAPSHOT_SCOPE):
            self.write(
                {
                    "bejerman_last_failure_at": fields.Datetime.now(),
                    "bejerman_last_failure_reason": reason,
                    "bejerman_failure_count": self.bejerman_failure_count + 1,
                }
            )
        try:
            with self.env.cr.savepoint():
                self._bejerman_notify_sync_failure(reason)
        except Exception as exc:
            _logger.warning(
                "Bejerman sync failure notice of connector %s could not be posted: %s",
                self.id,
                type(exc).__name__,
            )

    @api.private
    def _bejerman_sync_managers(self):
        """Internal Collections Managers of the connector's company."""
        self.ensure_one()
        group = self.env.ref(COLLECTION_MANAGER_GROUP).sudo()
        return group.all_user_ids.filtered(
            lambda user: not user.share and self.company_id in user.company_ids
        )

    @api.private
    def _bejerman_sync_notices(self):
        """Open outage notices on this connector."""
        self.ensure_one()
        activity_type = self.env.ref(SYNC_FAILED_ACTIVITY, raise_if_not_found=False)
        if not activity_type:
            return self.env["mail.activity"]
        return self.sudo().activity_ids.filtered(
            lambda activity: activity.activity_type_id == activity_type
        )

    @api.private
    def _bejerman_notify_sync_failure(self, reason):
        """One open notice per manager until the next successful refresh."""
        self.ensure_one()
        if self._bejerman_sync_notices():
            return
        managers = self._bejerman_sync_managers()
        if not managers:
            _logger.warning(
                "Bejerman sync failed for connector %s and no manager can be told",
                self.id,
            )
            return
        reason_field = self._fields["bejerman_last_failure_reason"]
        labels = dict(reason_field._description_selection(self.env))
        note = Markup("<p>%s</p>") % _(
            "The Bejerman debt snapshot of %(connector)s could not be refreshed "
            "(%(reason)s). Debt older than %(hours)s hours is refused to sellers "
            "and operators. Check the connector settings and the Bejerman "
            "server, then use Refresh Debt.",
            connector=self.name,
            reason=labels.get(reason, reason),
            hours=self.bejerman_snapshot_max_age_hours,
        )
        connector = self.sudo()
        for manager in managers:
            connector.activity_schedule(
                SYNC_FAILED_ACTIVITY, note=note, user_id=manager.id
            )

    @api.private
    def _bejerman_clear_sync_notices(self):
        """A successful refresh closes the outage notice."""
        self.ensure_one()
        self._bejerman_sync_notices().unlink()

    def action_bejerman_refresh_snapshot(self):
        """Refresh only after checking management access to this company."""
        self._check_collection_management_access()
        if self.type != "bejerman":
            raise UserError(_("The requested connector operation is not available."))
        # Credentials and server paths remain system-only; elevation is limited
        # to this checked connector and the fixed refresh operation.
        self.sudo()._bejerman_refresh_snapshot()
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
    def _bejerman_replace_snapshot(
        self, customers, debts, sellers, started_at=None, skipped=0
    ):
        self.ensure_one()
        Customer = self.env["collection.connector.bejerman.customer"]
        Debt = self.env["collection.connector.bejerman.debt"]
        Seller = self.env["collection.connector.bejerman.seller"]
        scope = [("connector_id", "=", self.id)]
        try:
            with self.env.cr.savepoint():
                Customer.search(scope).unlink()
                Debt.search(scope).unlink()
                Seller.search(scope).unlink()
                Customer.create([dict(row, connector_id=self.id) for row in customers])
                Debt.create([dict(row, connector_id=self.id) for row in debts])
                Seller.create([dict(row, connector_id=self.id) for row in sellers])
                now = fields.Datetime.now()
                with privileged(SNAPSHOT_SCOPE):
                    self.write(
                        {
                            "bejerman_snapshot_started_at": started_at or now,
                            "bejerman_snapshot_refreshed_at": now,
                            "bejerman_snapshot_customer_count": len(customers),
                            "bejerman_snapshot_debt_count": len(debts),
                            "bejerman_snapshot_skipped_count": skipped,
                            "bejerman_failure_count": 0,
                        }
                    )
        except Exception as exc:
            self._bejerman_refresh_failed(exc, reason="storage")

    @api.private
    def _collection_erp_reflected_since(self):
        """Bejerman data includes ERP entries made before its read started.

        The snapshot reflects what Bejerman held when its last successful refresh
        STARTED reading (a profile that reads debt live answers now). A refresh
        that started before a sheet was marked "Entered in the ERP" may predate
        the entry, so it releases nothing.
        """
        self.ensure_one()
        if self.type != "bejerman":
            return super()._collection_erp_reflected_since()
        return self.bejerman_snapshot_started_at or False

    @api.private
    def _bejerman_require_snapshot(self):
        """Fail closed before the first refresh instead of downloading inline."""
        self.ensure_one()
        if not self.bejerman_snapshot_refreshed_at:
            self._bejerman_misconfigured()

    @api.private
    def _bejerman_require_fresh_snapshot(self):
        """Refuse debt from a snapshot older than the connector's threshold."""
        self.ensure_one()
        self._bejerman_require_snapshot()
        hours = self.bejerman_snapshot_max_age_hours or DEFAULT_SNAPSHOT_MAX_AGE_HOURS
        age = fields.Datetime.now() - self.bejerman_snapshot_refreshed_at
        if age > timedelta(hours=hours):
            raise ConnectorDataStaleError(
                _(
                    "The customer debt is out of date: the last Bejerman update "
                    "is older than %(hours)s hours. Ask a collections manager to "
                    "check the Bejerman connection.",
                    hours=hours,
                )
            )

    @api.private
    def _bejerman_list_sellers(self):
        """Seller rows from the snapshot, merged with what Odoo maintains.

        Bejerman only supplies code and name. Commission is the binding's, the phone
        is the bound user's partner phone and ``active`` means the bound user is in
        the company's enabled sellers, so a later import never overwrites the admin's
        values. A seller with no binding yet is inactive, commission 0, no phone.
        Makes no Bejerman call.
        """
        self.ensure_one()
        self._bejerman_require_snapshot()
        sellers = self.env["collection.connector.bejerman.seller"].search(
            [("connector_id", "=", self.id)]
        )
        bindings = {
            binding.external_seller_id: binding for binding in self.seller_binding_ids
        }
        enabled = self.company_id.enabled_seller_ids
        rows = []
        for seller in sellers:
            binding = bindings.get(seller.seller_code)
            user = binding.user_id if binding else self.env["res.users"]
            rows.append(
                {
                    "id": seller.seller_code,
                    "name": seller.name or "",
                    "mobile": user.partner_id.phone or "",
                    "active": bool(user) and user in enabled,
                    "commission_percent": binding.commission_percent
                    if binding
                    else 0.0,
                }
            )
        return rows

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
    def _bejerman_invoice_payload(self, debt, today):
        """Sqlite-raw invoice row; ``state`` depends on today, so it is never stored.

        No ``amount_untaxed``: ``collection`` then pays commission on the total.
        """
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

    @api.private
    def _bejerman_get_customer_debt(self, external_seller_id, customer_identification):
        self.ensure_one()
        self._bejerman_require_fresh_snapshot()
        customers = self.env["collection.connector.bejerman.customer"].search(
            [
                ("connector_id", "=", self.id),
                ("seller_code", "=", mapping.trim_code(external_seller_id)),
            ]
        )
        customers = customers.filtered(
            lambda customer: mapping.matches_customer_query(
                customer.identification,
                customer.customer_code,
                customer_identification,
            )
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
            "invoices": [self._bejerman_invoice_payload(debt, today) for debt in debts],
            "credit_total": customers.credit_total,
            "as_of": fields.Datetime.to_string(self.bejerman_snapshot_refreshed_at),
        }
