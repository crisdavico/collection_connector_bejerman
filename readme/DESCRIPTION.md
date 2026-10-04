Read-only Bejerman seller, customer, and debt source for Collections.

Adds connector type `bejerman`. Each ERP read opens a SOAP session over a vendored httpx
client: Registro, then Ejecutar, then Cierre even when Ejecutar fails. Reads need TABLAS
`ObtenerClientes` plus the debt Queries view; missing grants fail closed.
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
stored snapshot in one transaction (`collection.connector.bejerman.debt`,
`collection.connector.bejerman.customer` and `collection.connector.bejerman.seller`).
The sellers are the voucher sellers (`CVEVEN_COD` / `VEN_DESC`) of every debt view row,
open or not, taken from that same download. A failed refresh keeps the previous snapshot.
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
snapshot. Test Connection probes Registro and `ObtenerClientes`, then Cierre; the debt
view is exercised by the refresh.

Sellers: Bejerman has no seller view, so `list_sellers` reads the seller snapshot and
makes no Bejerman call (before the first refresh it fails closed like the customer
reads). Bejerman supplies only the code and name; Odoo keeps the rest and
`list_sellers` merges it back so an import never overwrites the administrator's values:
commission is the seller binding's `commission_percent`, the phone is the bound user's
partner phone, and `active` means the bound user is in the company's enabled sellers.
A seller without a binding is listed inactive, commission 0, no phone. The generic
`collection` list drops inactive rows, so only bound and enabled sellers reach the
import. The Bejerman Seller Scenario and View fields are unused and hidden. On the
connector form, the commission of a seller binding is editable only for Bejerman
connectors (collections managers and administrators already hold write access on the
binding); the next import keeps it.
