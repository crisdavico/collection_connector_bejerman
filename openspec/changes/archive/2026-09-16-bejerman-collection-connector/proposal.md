# Proposal: Bejerman Collection Connector

## Intent

Admins need a live Bejerman seller/customer/debt source on `collection.connector`. The
adapter feeds Import and collection MCP reads; it must fail closed, hide
SOAP/credentials, and never write receipts to Bejerman.

## Scope

### In Scope

- AGPL-3 non-application `collection_connector_bejerman` (`depends: collection`);
  Seedian-tracked files (no `git-init`); `_inherit` + `selection_add` `bejerman`,
  `ondelete={'bejerman': 'cascade'}`
- Read ops only: `_bejerman_test_connection`, `_bejerman_list_sellers`,
  `_bejerman_list_customers`, `_bejerman_get_customer_debt` (raw dispatcher shapes)
- Vendored SOAP (session, redact, `ObtenerClientes`, `ObtenerJsonQueryVista`); record
  settings; HTTPS default; insecure override; timeout; Cierre; `httpx` in `pip.txt` +
  `external_dependencies`; `invoke img-build`
- Suffix-map Query keys; trim padded codes; AFIP CUIT `XX-XXXXXXXX-X` on rows and
  lookup; FC-style → invoice; order/budget codes → quotation; outstanding open/overdue
  only
- Admin credentials (`groups="base.group_system"`), masked password, Test Connection;
  inherit `collection.view_collection_connector_form`
- TransactionCase + mock `httpx`; no-leak; suffix/CUIT/seller isolation;
  `create_receipt` unavailable

### Out of Scope

- `_bejerman_create_receipt`, Bejerman writes, MCP/hooks/menus/sample data,
  nebula-agent, collection/sqlite/SDK edits, nested git

## Capabilities

> sdd-spec contract. Seedian `openspec/specs/` has no matching domain;
> `collection-connectors` (collection git) is not Modified here.

### New Capabilities

- `bejerman-collection-connector`: read-only Bejerman adapter for `collection.connector`

### Modified Capabilities

- None

## Approach

Mirror sqlite production. Dispatcher miss fail-closes writes. Test Connection:
Registro + `ObtenerClientes` + both Query views, then Cierre. Bejerman/httpx → generic
`UserError`; redact logs. Chain PRs if authored diff exceeds 400 lines.

## Affected Areas

| Area                                                     | Impact    | Description               |
| -------------------------------------------------------- | --------- | ------------------------- |
| `odoo/custom/src/private/collection_connector_bejerman/` | New       | Addon, SOAP, views, tests |
| `odoo/custom/dependencies/pip.txt`                       | Modified  | Add `httpx`; rebuild      |
| `collection/` dispatcher + formatters                    | Unchanged | Read-only                 |
| `collection_connector_sqlite/`, `Bejerman SDK/`          | Unchanged | Pattern source            |

## Risks

| Risk                                    | Likelihood | Mitigation              |
| --------------------------------------- | ---------- | ----------------------- |
| TABLAS/`ObtenerClientes` or Query views | High       | Apply/smoke gate        |
| Prefix leak in ids                      | Med        | Suffix tests            |
| Missing `httpx`                         | Med        | `external_dependencies` |
| Credential RPC                          | Med        | `base.group_system`     |
| CUIT mismatch                           | Med        | Canonicalize both       |
| >400 authored lines                     | High       | Chained PRs             |

## Rollback Plan

Uninstall the addon; drop `httpx` from `pip.txt` and rebuild. Cascade removes type
`bejerman`. MCP/allocation/sheet unchanged. Revert the Seedian commit.

## Dependencies

- Installed `collection`; Odoo 19 Doodba image with `httpx`
- Apply/smoke: ERP TABLAS/`ObtenerClientes` plus two Queries views (sellers + debt) with
  stable aliases (not a proposal block)

## Success Criteria

- [ ] Type `bejerman`; four read ops return sqlite-compatible raw rows; `create_receipt`
      raises generic `UserError`
- [ ] Admin-only masked credentials; Test Connection; no new menus/MCP; no leak of
      credentials, URLs, SOAP, view internals, or `ErrorMsg`
- [ ] CUIT, suffix mapping, padding trim, seller isolation, outstanding-only pass
- [ ] Module tests and scoped pre-commit pass after img-build
