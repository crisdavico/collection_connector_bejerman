# Design: Bejerman Collection Connector

## Technical Approach

Sibling AGPL-3 addon `collection_connector_bejerman` mirrors sqlite: `_inherit`
`collection.connector`, `selection_add` `bejerman` (cascade), four `@api.private`
`_bejerman_*` reads in sqlite raw shapes. Collection formatters/MCP untouched. Vendor
SOAP (no pip SDK, dotenv, CLI, Stock). Omit `_bejerman_create_receipt`. Seedian-tracked
files; no `git-init`. Apply/smoke gated on ERP grants; tests mock httpx and do not
assume live views.

## Architecture Decisions

| Option                      | Tradeoff                             | Decision                                                                                         |
| --------------------------- | ------------------------------------ | ------------------------------------------------------------------------------------------------ |
| Pip SDK vs vendor           | Py3.14 + dotenv + Stock              | Vendor session/soap/errors + `ObtenerClientes` + `ObtenerJsonQueryVista`; `Settings` from fields |
| Receipt stub vs omit        | Stale collection spec vs live sqlite | Omit `_bejerman_create_receipt`                                                                  |
| Nested git vs Seedian files | sqlite later split                   | Seedian-tracked; no `git-init`                                                                   |
| One vs two insecure flags   | SDK splits HTTP/TLS                  | One `bejerman_allow_insecure`: HTTP allowed + TLS verify off unless CA path set                  |
| Query filter JSON vs Python | View aliases unknown                 | Fetch configured views; suffix-map + filter in Python                                            |
| pytest-httpx vs unittest    | Odoo runner                          | `unittest.mock` of `httpx.Client.post`                                                           |

## Data Flow

```
op / Test Connection
  → _bejerman_client()  Settings from this record (HTTPS default)
  → BejermanClient.__enter__     POST Registro     token in memory
  → execute(TABLAS, ObtenerClientes) and/or
    execute(QUERIES, ObtenerJsonQueryVista)
  → BejermanClient.__exit__      POST CierreProceso  always (even if Ejecutar failed)
  → map/filter → raw rows | generic UserError (redact Token/xClave; never ErrorMsg)
```

Test Connection: Registro → ObtenerClientes → seller Query → debt Query → Cierre.
Refusal → generic admin `UserError`. Success uses collection's notification.

```
list_sellers        seller Query → suffix map, trim, drop inactive, commission 0–100
list_customers      ObtenerClientes → seller-scope, CUIT, drop inactive/other
get_customer_debt   ObtenerClientes match + debt Query → kind + outstanding
create_receipt      no method → dispatcher unavailable UserError; no POST
```

## File Changes

| File                                                                  | Action    | Description                       |
| --------------------------------------------------------------------- | --------- | --------------------------------- |
| `odoo/custom/src/private/collection_connector_bejerman/` (tree below) | Create    | Addon                             |
| `odoo/custom/dependencies/pip.txt`                                    | Modify    | Add `httpx`                       |
| `collection/models/collection_connector.py`                           | Unchanged | Read-only dispatcher/formatters   |
| `collection_connector_sqlite/**`                                      | Unchanged | Read-only inherit/no-leak pattern |
| `Bejerman SDK/bejerman_connector/**`                                  | Unchanged | Read-only SOAP source             |

```
collection_connector_bejerman/
  __init__.py  __manifest__.py  LICENSE
  readme/DESCRIPTION.md
  models/__init__.py
  models/collection_connector.py    inherit, fields, _bejerman_* ops
  service/__init__.py
  service/errors.py  soap.py  settings.py  session.py
  service/tablas.py             ObtenerClientes only
  service/queries.py            ObtenerJsonQueryVista only
  service/mapping.py            suffix, CUIT, kind, outstanding, trim
  views/collection_connector_views.xml
  tests/__init__.py
  tests/test_bejerman_connector.py
```

No `post_init_hook`, data XML, menus, MCP, or security CSV (inherit ACL). Manifest:
`depends: ["collection"]`, `application: False`, AGPL-3,
`external_dependencies: {"python": ["httpx"]}`, views only. `invoke img-build` before
install.

## Interfaces / Contracts

Credential/config fields: `groups="base.group_system"`. Password widget on clave (stored
Char). Type-gated inherit of `collection.view_collection_connector_form` (sqlite
pattern): Test Connection header `groups="base.group_system"`.

| Field                                                        | Role                                       |
| ------------------------------------------------------------ | ------------------------------------------ |
| `bejerman_ws_url`                                            | HTTPS default; HTTP only if allow-insecure |
| `bejerman_usuario` / `bejerman_clave`                        | Registro                                   |
| `bejerman_empresa` / `bejerman_puesto` / `bejerman_sucursal` | Registro                                   |
| `bejerman_timeout`                                           | httpx timeout (default 60)                 |
| `bejerman_allow_insecure`                                    | HTTP + skip TLS unless CA set              |
| `bejerman_ca_bundle`                                         | optional PEM path → `verify=`              |
| `bejerman_seller_scenario` / `_view`                         | sellers Query                              |
| `bejerman_debt_scenario` / `_view`                           | debt Query                                 |
| `bejerman_quotation_kinds`                                   | comma codes → `quotation`                  |

```python
def value_by_suffix(row, *suffixes):
    for suffix in suffixes:
        for key, val in row.items():
            if key == suffix or str(key).endswith(suffix):
                return val
    return None
```

CUIT: 11 digits → `XX-XXXXXXXX-X`; apply to rows and lookup before match. Trim: `strip`
plus leading-zero pad on seller/customer codes (keep `"0"`). Kind: upper startswith `FC`
→ invoice; in quotation set → quotation; else invoice. Outstanding: `balance > 0` and
`state in {open, overdue}` (formatter still filters). Catch Bejerman/httpx/JSON →
`_bejerman_misconfigured()` generic `UserError`; redact logs. Company isolation:
Settings/URL from `self` only.

## Testing Strategy

TransactionCase. Patch `service.session.httpx.Client.post` (not pytest-httpx). No live
ERP. Fixture SOAP OK/ErrorMsg/Fault. Assert Cierre SOAPAction after Ejecutar failure.
`_LEAK_TOKENS`: URL, user, clave, Token, SOAP tags, view names, SQL, `ErrorMsg`.

| Spec scenario                     | Test method                                         |
| --------------------------------- | --------------------------------------------------- |
| Type is selectable                | `test_bejerman_selection_add_and_cascade`           |
| Four ops return raw rows          | `test_four_ops_return_sqlite_raw_shapes`            |
| create_receipt fails closed       | `test_create_receipt_unavailable_no_post`           |
| Full probe then close             | `test_connection_probe_then_cierre`                 |
| Seller suffix map                 | `test_list_sellers_suffix_trim_zero_commission`     |
| Seller-scoped canonical customers | `test_list_customers_seller_scope_cuit`             |
| Kind and outstanding              | `test_get_customer_debt_kind_outstanding`           |
| Unknown customer                  | `test_get_customer_debt_unknown_empty`              |
| Prefixes stripped                 | `test_emitted_ids_omit_query_prefixes`              |
| Errors hide internals             | `test_errors_no_leak`                               |
| Admin-only masked credentials     | `test_admin_only_credentials_and_button`            |
| Isolation                         | `test_company_a_does_not_read_company_b`            |
| Missing grants fail closed        | `test_missing_obtener_clientes_or_view_fail_closed` |
| (lifecycle)                       | `test_session_cierre_on_ejecutar_failure`           |

## Threat Matrix

N/A — SOAP over httpx inside Odoo is not routing, shell, subprocess, VCS/PR automation,
executable-file classification, or process integration.

## Migration / Rollout

No data migration. `httpx` → `invoke img-build` → install. Uninstall cascades
`bejerman`. Rollback: uninstall, drop `httpx`, rebuild.

## Open Questions

None
