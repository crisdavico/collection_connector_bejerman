# Tasks: Bejerman Collection Connector

## Review Workload Forecast

| Field | Value |
| --- | --- |
| Estimated changed lines | 900–1400 |
| Suggested split | PR1 scaffold → PR2 SOAP → PR3 ops → PR4 views → PR5 docs |
| Delivery strategy | auto-chain |

Decision needed before apply: No
Chained PRs recommended: Yes
Chain strategy: stacked-to-main
400-line budget risk: High

### Suggested Work Units

| Unit | Goal | Likely PR | Focused test command | Runtime harness | Rollback boundary |
| --- | --- | --- | --- | --- | --- |
| 1 | httpx + scaffold + type | PR 1 | `invoke test -m collection_connector_bejerman --mode=update` | Same; `invoke img-build` after `httpx` (file/import OK before rebuild) | Addon tree + `pip.txt` `httpx` |
| 2 | Vendored SOAP + Cierre | PR 2 | same | same; mock `httpx.Client.post` | `service/{errors,soap,settings,session,tablas,queries}.py` |
| 3 | mapping + `_bejerman_*` | PR 3 | same | same | `service/mapping.py` + model ops |
| 4 | Admin form + ACL | PR 4 | same | same | `views/collection_connector_views.xml` |
| 5 | readme + lint + suite | PR 5 | same + scoped pre-commit | same; no live ERP | `readme/DESCRIPTION.md` |

## Phase 1: Doodba httpx + addon scaffold

- [x] 1.1 Append `httpx` to `/home/crisd/projects/seedian/seedian/odoo/custom/dependencies/pip.txt` (read-only). Done in parent Seedian repo; this git cannot acquire there because nested collection git dirs block the candidate.
- [x] 1.2 Create `odoo/custom/src/private/collection_connector_bejerman/{__init__.py,__manifest__.py,LICENSE,models/__init__.py,tests/__init__.py}` — AGPL-3, depends collection, not application, httpx extra, no git-init. Copy `odoo/custom/src/private/collection_connector_sqlite/LICENSE` (read-only).
- [x] 1.3 RED: `tests/test_bejerman_connector.py` `test_bejerman_selection_add_and_cascade`. Mirror `odoo/custom/src/private/collection_connector_sqlite/tests/test_sqlite_connector.py` (read-only).
- [x] 1.4 GREEN: `models/collection_connector.py` `_inherit` `collection.connector`, `selection_add` `bejerman`, `ondelete={'bejerman': 'cascade'}`. Dispatcher: `odoo/custom/src/private/collection/models/collection_connector.py` (read-only).

## Phase 2: Vendored SOAP client

- [x] 2.1 Vendor `service/{__init__,errors,soap,settings,session}.py` from `/home/crisd/projects/Bejerman SDK/bejerman_connector/src/bejerman_connector/` (read-only): record Settings; one `bejerman_allow_insecure`; no dotenv/CLI/Stock.
- [x] 2.2 Add `service/tablas.py` (`ObtenerClientes` only) and `service/queries.py` (`ObtenerJsonQueryVista` only) from `/home/crisd/projects/Bejerman SDK/bejerman_connector/src/bejerman_connector/operations/` (read-only).
- [x] 2.3 RED: `test_session_cierre_on_ejecutar_failure` — Cierre after Ejecutar fail; redact Token/xClave; patch `service.session.httpx.Client.post`.
- [x] 2.4 GREEN: `service/session.py` `__exit__` always POSTs Cierre; redact logs; never quote `ErrorMsg`.

## Phase 3: Mapping and read ops

- [x] 3.1 RED then GREEN `service/mapping.py`: `value_by_suffix`, trim pad (keep `"0"`), CUIT `XX-XXXXXXXX-X`, FC→invoice, quotation set, outstanding only.
- [x] 3.2 RED: `test_four_ops_return_sqlite_raw_shapes`, `test_create_receipt_unavailable_no_post`. Raw keys: `odoo/custom/src/private/collection_connector_sqlite/models/collection_connector.py` (read-only).
- [x] 3.3 RED: `test_connection_probe_then_cierre`, `test_missing_obtener_clientes_or_view_fail_closed`.
- [x] 3.4 RED: `test_list_sellers_suffix_trim_zero_commission`, `test_list_customers_seller_scope_cuit`, `test_get_customer_debt_kind_outstanding`, `test_get_customer_debt_unknown_empty`, `test_emitted_ids_omit_query_prefixes`, `test_company_a_does_not_read_company_b`.
- [x] 3.5 GREEN: `@api.private` `_bejerman_test_connection`, `_bejerman_list_sellers`, `_bejerman_list_customers`, `_bejerman_get_customer_debt` plus config fields on `models/collection_connector.py`. Omit `_bejerman_create_receipt`. Probe then Cierre. Catch faults → `_bejerman_misconfigured()`; Settings from `self`.

## Phase 4: Admin views and ACL

- [x] 4.1 RED: `test_admin_only_credentials_and_button`, `test_errors_no_leak` (`_LEAK_TOKENS`: URL, user, clave, Token, SOAP, views, SQL, ErrorMsg). Pattern: `odoo/custom/src/private/collection_connector_sqlite/views/collection_connector_views.xml` (read-only).
- [x] 4.2 GREEN: `views/collection_connector_views.xml` inherit `collection.view_collection_connector_form`; type-gated fields; password widget; Test Connection `groups="base.group_system"`. No menus/MCP/hooks/data/ACL CSV.
- [x] 4.3 GREEN: credential fields `groups="base.group_system"`; UserError omits `_LEAK_TOKENS`.

## Phase 5: Docs and quality

- [x] 5.1 Write `readme/DESCRIPTION.md` (OCA fragment only).
- [x] 5.2 `pre-commit run --files odoo/custom/src/private/collection_connector_bejerman/** odoo/custom/dependencies/pip.txt`.
- [x] 5.3 `invoke test -m collection_connector_bejerman --mode=update` (mock httpx; live ERP is apply/smoke).
