## Exploration: Bejerman collection connector (read-only)

Confirmed product decisions are recorded, not reopened: new AGPL-3 non-application addon
`collection_connector_bejerman` depending on `collection`; `selection_add` type
`bejerman`; no hooks, sample ERP data, MCP, menus, or Bejerman writes; SOAP client
vendored from the SDK (session, parse/redact, errors, `ObtenerClientes`,
`ObtenerJsonQueryVista` only); settings on the connector record; `httpx` in Doodba
`pip.txt` plus manifest `external_dependencies`.

### Current State

**Dispatcher (read-only).** `collection.connector.type` is an empty Selection. Public
`test_connection` / `list_sellers` / `list_customers` / `get_customer_debt` /
`create_receipt` call `_dispatch(op)`, which allowlists `_DISPATCH_OPS` (those five
names), checks the type is a live Selection key, then `getattr(self, f"_{type}_{op}")`.
Missing callable → generic `UserError`
(`The requested connector operation is not available.`). Empty/unknown type →
`The collection connector is not configured.` Adapters never format MCP payloads: they
return **raw** rows; `_format_seller_list`, `_format_customer_list`, and
`_format_customer_debt` drop inactive rows, outstanding filter (`balance > 0` and
`state in {open, overdue}`), default empty `document_kind` to `invoice`, and attach
`source` (MCP strips `source`). Close does **not** call `create_receipt` (local Close
since 2026-09-08).

**Raw shapes before `_format_*` (from sqlite + test provider):**

| Op                                                      | Return                                                                                                                                                                                                                                                                                                                                                |
| ------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `list_sellers`                                          | list of `{id, name, mobile, active, commission_percent}`                                                                                                                                                                                                                                                                                              |
| `list_customers(external_seller_id)`                    | list of `{id, name, identification, customer_code, active}` seller-scoped                                                                                                                                                                                                                                                                             |
| `get_customer_debt(external_seller_id, identification)` | `{customer: {id, name, identification, customer_code, active} \| None, invoices: [{id, number, issue_date, due_date, amount, balance, state, document_kind}]}`. Zero or many customer matches → `{customer: None, invoices: []}` so the formatter raises the generic customer `UserError`. Unknown `document_kind` is coerced to `invoice` in sqlite. |
| `test_connection`                                       | truthy; public method wraps success as a client notification                                                                                                                                                                                                                                                                                          |

Seller-scoped customer/debt calls receive the **bound external** seller id after
`_enabled_bound_external_seller_id`. Identification is strip-only in collection;
matching is exact. Partner `vat` is stored as that identification string.

**SQLite parallel.** `_inherit` +
`selection_add=[("sqlite", "SQLite")], ondelete={"sqlite": "cascade"}`; Char path;
`@api.private` `_sqlite_*`; generic `_sqlite_misconfigured()`; form inherit adds admin
`Test Connection` (`groups="base.group_system"`) and type-gated fields. Tests assert no
leak of SQL, `sqlite3`, paths, or `.db` in `UserError`. Sample DB + `post_init_hook`
exist here; Bejerman must **not** copy that. **No `_sqlite_create_receipt`** in
production code. Collection OpenSpec still requires a sqlite receipt stub; that is spec
drift. Live behavior is dispatcher miss → `UserError`. Collection tests stub receipts
only on the in-test `type="test"` provider.

**Pluggable-connectors archive (2026-08-26).** Settled provider-record + `_<type>_*`
dispatch; sqlite as a sibling addon; ACL `group_user` read / `group_system` write; never
`sudo()`. SQLite was originally planned as **parent Seedian files**; it later became its
own git (`collection_connector_sqlite.git`). Collection remains `nebula_odoo.git`.

**Bejerman SDK (no CodeGraph index; Read/Grep).** `BejermanClient` context manager:
Registro → token in memory → `execute(circuito, operacion, parametros_json)` →
CierreProceso in `__exit__` even when Ejecutar failed. SOAP 1.1, no zeep/WSDL.
`redact_soap` masks Token/`xClave`. HTTPS + cert verify by default; HTTP needs an
explicit insecure flag; optional CA bundle. `ObtenerClientes` is `TABLAS` + `{}` and
returns a list whose first row includes `Cliente_Codigo`. Customer master fields include
`Cliente_CUIT` (11 digits), `Cliente_Habilitado`, `Cliente_VendedorCodigo` (4, often
padded). `ObtenerJsonQueryVista` is `QUERIES` with `[escenario, vista]` or a third
JSON-string filters element (`Campo` / `Valor`). Query JSON keys are view-generated
(prefixes / `CpoCalc_`); product aliases are **suffixes**. SDK package is Python 3.14 +
dotenv + CLI + Stock — none of that belongs in Odoo 19/Doodba.

**Doodba.** `odoo/custom/dependencies/pip.txt` has `pysimplesoap` (pyafipws/ARCA), not
`httpx`. Adding `httpx` requires `invoke img-build`. Private addons under
`odoo/custom/src/private/` load without `addons.yaml`. Connector ACL already covers
inherited fields; credential fields still need `groups="base.group_system"` so
`group_user` read on the model cannot RPC the password.

**Apply gate (do not live-call).** Account can Registro but currently refuses
`ObtenerClientes`. Two Queries views with stable aliases are still required (sellers +
debt). That blocks apply/smoke, not proposal.

### Affected Areas

- `odoo/custom/src/private/collection_connector_bejerman/` — **create** (does not
  exist): manifest, inherit, vendored SOAP, views, tests, readme fragments.
- `odoo/custom/dependencies/pip.txt` — add `httpx`; image rebuild.
- `odoo/custom/src/private/collection/models/collection_connector.py` — **read-only**
  dispatcher + formatters; do not edit.
- `odoo/custom/src/private/collection_connector_sqlite/` — **read-only** pattern source
  (inherit, fail-closed, no-leak tests). Do not copy sample hooks.
- `Bejerman SDK/bejerman_connector/src/bejerman_connector/` — **read-only** SOAP source
  to adapt (session, soap, errors, config without dotenv, tablas/queries).
- `collection/openspec/specs/collection-connectors/spec.md` — **read-only**; sqlite
  `create_receipt` stub requirement is stale vs code. Do not “fix” it in this change.

### Approaches

1. **Sibling addon + vendored read-only SOAP (settled)** — Mirror sqlite: `_inherit` /
   `selection_add` `bejerman` with `ondelete={'bejerman': 'cascade'}`;
   `_bejerman_test_connection`, `_bejerman_list_sellers`, `_bejerman_list_customers`,
   `_bejerman_get_customer_debt` only. Vendor a trimmed client inside the addon
   (record-built `Settings`, no `.env`, no Stock/CLI). Map Query keys by alias suffix;
   trim padded codes; canonicalize 11-digit CUITs to AFIP `XX-XXXXXXXX-X` (matches
   collection fixtures) and normalize the debt lookup the same way before match. Scope
   customers with `Cliente_VendedorCodigo` vs trimmed external seller id. Map `FC`-style
   `DOCUMENT_KIND` → `invoice`, configured order/budget codes → `quotation`, else
   `invoice` (sqlite). Pre-filter outstanding; formatter still filters. Catch all
   Bejerman/httpx errors → generic translated `UserError`; redact in logs; always
   Cierre. Omit `_bejerman_create_receipt` so dispatch fail-closes writes.

   - Pros: Matches sqlite/MCP contracts; keeps collection storage-agnostic; HTTPS/TLS
     policy stays in one client; no write surface.
   - Cons: Image rebuild for `httpx`; ERP views + `ObtenerClientes` ACL are operational
     gates; Query prefixes must be suffix-mapped in tests.
   - Effort: Medium (likely over the 400-line review budget — SOAP + mapping + tests).

2. **Pip-install `bejerman_connector`** — Depend on the SDK package as-is.

   - Pros: Less copy.
   - Cons: Python 3.14 vs Doodba Odoo 19; dotenv/CLI/Stock; settings from env not the
     connector record. Rejected by confirmed product decisions.
   - Effort: Low, unsafe.

3. **Implement `_bejerman_create_receipt` because `_DISPATCH_OPS` includes it** — Stub
   like the **stale** collection spec / test provider.
   - Pros: Satisfies archived CONN-02 wording.
   - Cons: Live sqlite has no stub; Close never dispatches; product forbids Bejerman
     writes; a stub invites a later real write. Dispatcher already fail-closes.
   - Effort: Low, out of scope.

### Recommendation

Ship **approach 1**. Treat sqlite production code (not the stale receipt-stub spec) as
the adapter contract. Start the addon as **Seedian-tracked files** under
`odoo/custom/src/private/collection_connector_bejerman/` (the original sqlite delivery
in the 2026-08-26 design). Do **not** `git-init` now: `apply.roots` already target that
path plus `odoo/custom/dependencies`; a third nested repo before first merge repeats
sqlite’s later split without benefit. Independent git can wait until the addon has a
stable versioning story.

**Test Connection:** Registro + `ObtenerClientes` (the permission gate) + both
configured Query views, then Cierre. Any refusal → generic admin `UserError`, success
notification unchanged from collection.

**Admin fields (system group, type-gated, password widget on clave):** WS URL, user,
password, company, workstation, branch, timeout, allow-insecure HTTP/TLS, optional CA
bundle path, seller/debt scenario + view names, quotation `DOCUMENT_KIND` codes. No new
menu (inherit `collection.view_collection_connector_form` like sqlite).

**Tests:** TransactionCase + `unittest.mock` of `httpx.Client.post` (Odoo runner, not
`pytest-httpx`). Assert suffix mapping, CUIT canonicalization, padding trim, seller
scope, outstanding-only, fail-closed, and no leak of credentials, URLs, SOAP, SQL/view
internals, or Bejerman `ErrorMsg`. Assert `create_receipt` on type `bejerman` raises the
generic unavailable `UserError`.

**Apply still waits** on working `ObtenerClientes` and the two Query views. Proposal can
proceed; live smoke cannot.

### Risks

- Current Bejerman account registers but refuses `ObtenerClientes` — Test Connection,
  customer list, and smoke stay blocked until ERP grants TABLAS read.
- Required Query views/aliases do not exist yet; prefixes will leak into ids if suffix
  mapping is skipped.
- `httpx` needs `invoke img-build`; module install fails until the image has it
  (`external_dependencies`).
- `pysimplesoap` in `pip.txt` is unrelated (AFIP); do not reuse it for Bejerman SOAP.
- `group_user` can read `collection.connector`; credential fields without
  `groups="base.group_system"` would leak via RPC.
- Authored SOAP + mapping + no-leak tests likely exceed the 400-line review budget —
  propose/tasks should forecast chained PRs (client vs adapter vs tests).
- Nested git: collection and sqlite are separate remotes; committing the new addon into
  those trees would be wrong.
- CUIT canonicalization must apply to both stored rows and the lookup argument or
  `customer_debt` misses on dashed vs digits.

### Ready for Proposal

**Yes.** Product decisions are confirmed and match live dispatcher/sqlite/SDK code.
Propose should lock: sibling addon, vendored read-only SOAP, omit receipt stub, Seedian
tracked files (no git-init), `httpx` + img-build, fail-closed/no-leak, and the ERP
prerequisite as an apply/smoke gate — not a proposal interview. Do not reopen mixin
overrides, company-as-config, Bejerman writes, or MCP in this addon.
