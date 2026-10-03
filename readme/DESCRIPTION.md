Read-only Bejerman seller, customer, and debt source for Collections.

Adds connector type `bejerman`. Each ERP read opens a SOAP session over a vendored httpx
client: Registro, then Ejecutar, then Cierre even when Ejecutar fails. Reads need TABLAS
`ObtenerClientes` plus two Queries views (sellers and debt); missing grants fail closed.
There is no receipt write-back, no MCP, no menus, no sample ERP data, and no
`post_init_hook`. Depends on `collection`. Requires the `httpx` Python extra.
Credentials and Test Connection are Settings-only (`base.group_system`); clave is
password-masked. Faults raise a generic `UserError` with no SOAP, Token, URL, user, or
clave. Customer listing and customer debt are seller-scoped and stay in this addon;
`collection` does not call Bejerman.

Debt snapshot: the debt view (`Saldos al día/*`, one row per sales voucher) is a ~200 MB
download, so it is never read per question. A refresh downloads the customers and the
debt view in one session, keeps only vouchers with a positive local-currency balance
(`CVE_SALDOMONLOC > 0`; reconciled and credit-note rows are dropped), and replaces the
stored snapshot in one transaction (`collection.connector.bejerman.debt` and
`collection.connector.bejerman.customer`). A failed refresh keeps the previous snapshot.
Refresh runs every 4 hours (`ir.cron`) and from the administrator-only **Refresh Debt**
button; the connector form shows the last refresh time and row counts. Before the first
refresh, `list_customers` and `get_customer_debt` fail closed with the generic "not
configured" error rather than downloading inline.

Customer debt reads the snapshot: voucher type `PRE` (configurable through Bejerman
Quotation Kinds, default `PRE`) is a `quotation`, every other type an `invoice`; the
external id is the stable `type|point|letter|number` key; `state` is `overdue` when the
due date is before today in the company timezone, else `open`, computed at read time.
Optionally, set Bejerman Debt Filter Field (for example `CVE_CODCLI`) once the ERP
exposes a filterable child view: debt is then read live per customer instead of from the
snapshot. Test Connection probes Registro, `ObtenerClientes`, and the seller view, then
Cierre; the debt view is exercised by the refresh.
