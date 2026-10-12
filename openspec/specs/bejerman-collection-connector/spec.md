# Bejerman Collection Connector Specification

## Purpose

Read-only Bejerman adapter for `collection.connector`. Sqlite-compatible raw reads; fail
closed; no receipt writes. Customer and debt reads are served from a periodically
refreshed snapshot because the debt view is a ~200 MB download.

## Requirements

### Requirement: Type registration

MUST inherit `collection.connector`, `selection_add` `bejerman`, cascade on uninstall.

#### Scenario: Type is selectable

- GIVEN installed addon
- WHEN creating a connector then uninstalling
- THEN `bejerman` MUST be valid until uninstall cascades it

### Requirement: Raw read operations

MUST implement `test_connection`, `list_sellers`, `list_customers`, and
`get_customer_debt` as sqlite raw shapes for `_format_*`. MUST NOT format MCP payloads.

#### Scenario: Four ops return raw rows

- GIVEN working bejerman connector
- WHEN the four read ops run
- THEN sqlite raw keys MUST match without MCP `source`

### Requirement: Receipt write unavailable

MUST NOT implement `create_receipt`; dispatch MUST raise generic unavailable `UserError`
with no write.

#### Scenario: create_receipt fails closed

- GIVEN a bejerman connector
- WHEN `create_receipt` is dispatched
- THEN MUST raise that `UserError` with no Bejerman write

### Requirement: Test Connection

MUST close the session after the probe. Success requires Registro and ObtenerClientes;
there is no seller view. The debt view MUST NOT be downloaded by Test Connection; the
snapshot refresh exercises it. Refusal MUST raise a generic admin `UserError`.

#### Scenario: Cheap probe then close

- GIVEN working TABLAS
- WHEN Test Connection runs
- THEN it MUST succeed, MUST NOT request the debt view, and MUST close the session

### Requirement: Real ERP payload handling

A Query view answer that is a JSON string holding the JSON rows MUST be decoded once; an
undecodable string MUST raise a transport error without quoting the payload.
`ObtenerClientes` MUST send an empty JSON list as parameters.

#### Scenario: JSON-in-JSON view answer

- GIVEN a Query view whose `DatosJSON` decodes to a string containing the row list
- WHEN the view is read
- THEN the rows MUST be returned as a list

### Requirement: Seller mapping

Bejerman has no seller view. Sellers MUST come from every row of the debt view the
snapshot refresh already downloads (`CVEVEN_COD` code, `VEN_DESC` name), mapped by alias
suffix, codes trimmed, unique, blank codes skipped, ambiguous aliases fail closed. They
MUST be stored in the same atomic swap as customers and debt, with no extra Bejerman
request. `list_sellers` MUST read that snapshot (generic "not configured" error before
the first refresh) and MUST NOT call Bejerman. Commission, phone and enabled state MUST
be Odoo's (binding `commission_percent`, bound user's partner phone, company enabled
sellers); a seller with no binding MUST be listed inactive with commission 0.

#### Scenario: Seller list from the snapshot

- GIVEN a refreshed snapshot, one bound enabled seller and one unbound seller
- WHEN `list_sellers` runs
- THEN no Bejerman request MUST be made; the bound seller MUST carry Odoo's commission,
  phone and active; the other MUST be inactive with commission 0

### Requirement: Seller-scoped customers

`list_customers` MUST be seller-scoped with AFIP CUIT `XX-XXXXXXXX-X` on rows and
lookup; omit other-seller and inactive.

#### Scenario: Seller-scoped canonical customers

- GIVEN mixed customers for E and others, plus 11-digit CUITs
- WHEN `list_customers` runs for E
- THEN only E's active customers MUST appear with canonical CUIT

### Requirement: Debt row mapping

Real `Saldos al día` rows (one per sales voucher, keys `<generated prefix><alias>`) MUST
map by exact alias suffix; an alias matching more than one key MUST drop the row. Only
rows with `CVE_SALDOMONLOC` > 0 are open; zero and negative rows MUST be dropped from the
open debt, and each customer's negative balances (credit notes, advances; same customer
filters, first id wins) MUST be summed, as a positive amount, into its `credit_total`
(decision D4). A row whose balance or amount cannot be read (blank, text, NaN) MUST be
skipped and counted, never mapped as 0; a refresh stores the count in
`bejerman_snapshot_skipped_count` and logs it without the values.
`amount` MUST be `CVE_IMPMONLOC` and `balance` `CVE_SALDOMONLOC`. The external id MUST
be `CVETCO_COD|CVE_CODPVT|CVE_LETRA|CVE_NRO`, each part stripped. `number` MUST be the
human form (`FHK A 00004-00001234`) with blank parts omitted. Dates MUST be ISO
`YYYY-MM-DD`. Voucher types listed in Bejerman Quotation Kinds (blank means `PRE`) MUST
map to `quotation`; every other type MUST map to `invoice`.

#### Scenario: Open invoice row

- GIVEN a row of type `FHK`, point `00004`, letter `A`, number `00001234`, balance 500
- WHEN it is mapped
- THEN id MUST be `FHK|00004|A|00001234`, number `FHK A 00004-00001234`, kind `invoice`

#### Scenario: Blank parts and quotation

- GIVEN a `PRE` row with a blank letter, and an `SID` row with blank point and letter
- WHEN they are mapped
- THEN ids MUST be `PRE|00004||00000077` and `SID|||00000005`, kinds `quotation` and
  `invoice`

#### Scenario: Reconciled and credit notes

- GIVEN rows with balance 0 and balance -50
- WHEN the debt is mapped
- THEN both MUST be omitted from the invoices
- AND the -50 row MUST add 50 to that customer's `credit_total`

### Requirement: Debt snapshot refresh

A refresh MUST read `ObtenerClientes` and the debt view inside one Registro, Ejecutar,
Cierre session, and MUST replace the connector's customer and debt rows in one
transaction. Duplicate external ids MUST keep the first row. Any failure MUST leave the
previous snapshot and its counters unchanged and MUST raise a generic `UserError` with
no SOAP, URL, credential, or `ErrorMsg` text in the error or the log. The connector MUST
record the refresh time and the customer and debt row counts.

#### Scenario: Successful refresh

- GIVEN a working ERP
- WHEN a refresh runs
- THEN the previous rows MUST be replaced and the refresh time and counts MUST be stored

#### Scenario: Failed refresh keeps the snapshot

- GIVEN a stored snapshot and an ERP failure or a database error during the swap
- WHEN a refresh runs
- THEN it MUST raise the generic refresh error and the previous rows MUST remain

### Requirement: Refresh entry points

An `ir.cron` MUST refresh every active Bejerman connector every 4 hours, isolating each
connector so one failure does not stop the others. The connector form MUST offer a
Refresh Debt button for `base.group_system` only, and the action MUST refuse other users
server side.

#### Scenario: Cron isolation

- GIVEN two Bejerman connectors and one failing refresh
- WHEN the cron runs
- THEN the healthy connector MUST still be refreshed

#### Scenario: Button is admin-only

- GIVEN a non-system user
- WHEN the refresh action is called
- THEN it MUST raise `AccessError` and MUST NOT contact the ERP

### Requirement: Snapshot reads

`list_customers` and `get_customer_debt` MUST read the stored snapshot and MUST NOT call
the ERP. `state` MUST be `overdue` when the due date is before today in the company
timezone, else `open`, computed at read time and never stored. Before the first refresh
both MUST fail closed with the generic not-configured `UserError`. Unknown, inactive, or
other-seller customers MUST return `{customer: None, invoices: []}`. Snapshot rows MUST
be company-scoped by an `ir.rule`, readable by `collection.group_collection_user` (not
by plain internal users), and writable by `base.group_system` only; reading them MUST NOT
require credential access. Snapshot and live debt answers MUST carry the customer's
`credit_total` and `as_of` (the snapshot's refresh time, or the read time on the live
path).

#### Scenario: Debt from the snapshot

- GIVEN a refreshed snapshot with open FHK, PRE, and SID rows for customer E
- WHEN `get_customer_debt` runs
- THEN the three rows MUST be returned with computed `state` and no ERP call

#### Scenario: No snapshot yet

- GIVEN a connector that was never refreshed
- WHEN `get_customer_debt` runs
- THEN MUST raise the generic not-configured `UserError` and MUST NOT call the ERP

#### Scenario: Unknown customer

- GIVEN unknown identification
- WHEN `get_customer_debt` runs
- THEN MUST return `{customer: None, invoices: []}`

### Requirement: Optional live filtered debt

When Bejerman Debt Filter Field is set, `get_customer_debt` MUST read that customer's
debt live from the debt view with the filter
`[{"Campo": <field>, "Valor": <ERP customer code>}]` instead of the snapshot, and MUST
NOT require a snapshot. The credentials MUST be used on behalf of non-admin callers
without being exposed to them.

#### Scenario: Live filter

- GIVEN a connector with filter field `CVE_CODCLI`
- WHEN `get_customer_debt` runs for a known customer
- THEN the debt view request MUST carry the customer filter and only that customer's
  open rows MUST be returned

### Requirement: Prefix-free identifiers

Query-generated prefixes MUST NOT appear in emitted ids or codes.

#### Scenario: Prefixes stripped

- GIVEN Query keys with generated prefixes
- WHEN sellers, customers, or debt rows are emitted
- THEN emitted ids MUST omit generated prefixes

### Requirement: No leakage

Credentials, URLs, SOAP, SQL/view internals, and Bejerman ErrorMsg MUST NOT appear in
`UserError` or MCP-visible messages.

#### Scenario: Errors hide internals

- GIVEN SOAP, view, or credential failure
- WHEN any bejerman op raises
- THEN UserError and MCP-visible text MUST omit those internals

### Requirement: Admin-only credentials

Credentials and Test Connection MUST be `base.group_system` with masked password. MUST
inherit collection connector form. MUST NOT add menus, MCP, hooks, sample data, or
Bejerman writes. The snapshot cron and its data records are allowed.

#### Scenario: Admin-only masked credentials

- GIVEN a non-system user and a system administrator
- WHEN they open a bejerman connector
- THEN only the administrator MUST see masked credentials and Test Connection

### Requirement: Company isolation

Reads MUST use the connector of `env.company`. A MUST NOT receive B's Bejerman data.

#### Scenario: Isolation

- GIVEN B's bejerman connector is not selected by A
- WHEN A lists or reads debt
- THEN the result MUST NOT come from B's connector

### Requirement: Missing ERP grants

Missing ObtenerClientes or either Query view MUST fail closed with a generic
`UserError`.

#### Scenario: Missing grants fail closed

- GIVEN refused ObtenerClientes or a missing Query view
- WHEN Test Connection or a read op runs
- THEN MUST raise a generic `UserError` with no leak

### Requirement: Retries within a deadline

The SOAP session MUST retry transient failures up to 3 attempts with exponential backoff
and equal jitter, honouring a sane `Retry-After` capped at 30 s. Reads (ObtenerClientes,
ObtenerJsonQueryVista) MUST retry on connect errors, timeouts, dropped connections, HTTP
429, and 5xx; Registro MUST retry only when the server cannot have processed it (connect
errors, 429, 503); CierreProceso MUST NOT retry. One session MUST finish within the
admin-only `bejerman_deadline` (default 900 s): no request starts past it, each request
timeout is capped by the time left, a retry that would pass it is not attempted, and
answers are read in chunks against it. The HTTP client MUST be closed on every path,
including a failed login.

#### Scenario: Lost login answer is not retried

- GIVEN Registro fails with a read timeout after the request was sent
- WHEN the session opens
- THEN Registro MUST NOT be sent again
- AND the HTTP client MUST be closed

### Requirement: Sync status and stale debt

Each connector MUST record the start and end of its last successful refresh and the time,
generic reason class, and count of failed scheduled refreshes; only a refresh writes
them. On a cron failure every Collections Manager of the company MUST get one "Bejerman
sync failed" activity on the connector; later failures MUST add none and the next
successful refresh MUST remove it. The cron MUST NOT fail (a notice that cannot be
posted is logged and skipped). Debt read from a snapshot older than
`bejerman_snapshot_max_age_hours` (default 24, minimum 1, set by managers) MUST raise
`ConnectorDataStaleError` with a generic message; the live filtered path has no age
limit.

#### Scenario: Old snapshot refused

- GIVEN a snapshot from a refresh 30 hours old and a maximum age of 24
- WHEN `get_customer_debt` runs
- THEN MUST raise the generic "out of date" `UserError` and MUST NOT return invoices

### Requirement: ERP-entered sheets released after the next refresh

`_collection_erp_reflected_since()` MUST return the start of the last successful snapshot
refresh, or now on the live filtered path. A sheet marked Entered in the ERP in
`collection` MUST stop reserving its applied amounts against Bejerman balances only once
a refresh that started after the mark succeeded; a refresh that started earlier, even if
it finished later, or a failed one, MUST release nothing.

### Requirement: Seller enable wizard

From the connector's Sellers tab, administrators and Collections Managers MAY enable a
snapshot seller: pick an internal user that already belongs to the connector's company
(the server MUST refuse any other user, so enabling never adds company access) or create
one in that company, set the phone and commission, then bind the user, write the phone
on the user's partner as the current user without `sudo()` (only when it changed; a
`UserError` asking an administrator to set it when the manager may not edit that
contact, checked before any other write), and add the user to the enabled sellers. A
user bound to another code or a phone used by another enabled seller MUST be refused.
Disable seller MUST remove the user from the enabled sellers and keep the binding.

#### Scenario: User from another company refused

- GIVEN a Collections Manager and an internal user who does not belong to the connector's
  company
- WHEN the wizard is confirmed for that user (even over RPC)
- THEN MUST raise `UserError` and MUST NOT create a binding or enable the seller
