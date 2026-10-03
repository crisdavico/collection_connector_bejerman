# Apply Progress: Bejerman Collection Connector

**Change**: bejerman-collection-connector **Mode**: Strict TDD **Work unit**: Phase 1
(PR 1 scaffold + type) — tasks 1.1–1.4 **Delivery**: auto-chain, stacked-to-main
**Attempt token**:
sha256:06c55c2ad9ebc98df0a16d2e9a23c28e8a5d576204cd8794f3c12493d168eba7 **Updated**:
2026-09-16

## Completed Tasks

- [x] 1.1 Append `httpx` to parent Seedian `odoo/custom/dependencies/pip.txt` (read-only
      from this git). Done before this apply batch.
- [x] 1.2 Addon scaffold: `__init__.py`, `__manifest__.py`, `LICENSE` (copied from
      sqlite), `models/__init__.py`, `tests/__init__.py`. AGPL-3,
      `depends: ["collection"]`, `application: False`,
      `external_dependencies.python: ["httpx"]`. No git-init.
- [x] 1.3 RED: `tests/test_bejerman_connector.py`
      `test_bejerman_selection_add_and_cascade`.
- [x] 1.4 GREEN: `models/collection_connector.py` `_inherit` `collection.connector`,
      `selection_add` `bejerman`, `ondelete={"bejerman": "cascade"}`.

## TDD Cycle Evidence

| Task | Test File                          | Layer                              | Safety Net           | RED                                                                                                                                      | GREEN                                                                                                       | TRIANGULATE                                                                                         | REFACTOR                                              |
| ---- | ---------------------------------- | ---------------------------------- | -------------------- | ---------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------- | ----------------------------------------------------- |
| 1.2  | N/A (scaffold)                     | Structural                         | N/A (new)            | N/A structural                                                                                                                           | N/A structural                                                                                              | ➖ Skipped: LICENSE/manifest/init files, one possible layout                                        | ➖ None needed                                        |
| 1.3  | `tests/test_bejerman_connector.py` | Integration (Odoo TransactionCase) | N/A (new)            | ✅ Written + executed: `AssertionError: 'bejerman' not found in {'sqlite'}` (`invoke test -m collection_connector_bejerman --mode=init`) | See 1.4                                                                                                     | ✅ Two paths in one method (sqlite mirror): selection+create vs ondelete cascade + manifest depends | ➖ None needed                                        |
| 1.4  | `tests/test_bejerman_connector.py` | Integration (Odoo TransactionCase) | N/A (new model file) | Inherited from 1.3 (production `selection_add` did not exist)                                                                            | ✅ Passed: `0 failed, 0 error(s) of 1 tests` (`invoke test -m collection_connector_bejerman --mode=update`) | ✅ Same method: selectable type create, cascade registry, `depends` includes `collection`           | ➖ None needed — inherit is the sqlite-shaped minimum |

### Test Summary

- **Total tests written**: 1 (`test_bejerman_selection_add_and_cascade`)
- **Total tests passing**: 1 (Odoo also reports `3 tests` in stats for setup/teardown
  accounting; result line is `0 failed, 0 error(s) of 1 tests`)
- **Layers used**: Unit (0), Integration (1), E2E (0)
- **Approval tests** (refactoring): None — no refactoring tasks
- **Pure functions created**: 0

Triangulation skipped for 1.2 only: purely structural scaffold (no branching, no logic).

## Work Unit Evidence

| Evidence                                          | Required value                                                                                                                                                                                                                                                                                 |
| ------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Focused test command and exact result             | `invoke test -m collection_connector_bejerman --mode=update` from Seedian root → exit 0; `0 failed, 0 error(s) of 1 tests when loading database 'devel'`; `Starting TestBejermanConnector.test_bejerman_selection_add_and_cascade`                                                             |
| Runtime harness command/scenario and exact result | New addon was not installed: `--mode=update` first ran **0 tests**. `--mode=init` after `invoke img-build` (httpx missing in image) installed the module. RED: exit 1, `'bejerman' not found in {'sqlite'}`. GREEN: `--mode=update` exit 0, 1/1 passing. Also `invoke start` (stack was down). |
| Rollback boundary                                 | This addon git: `__init__.py`, `__manifest__.py`, `LICENSE`, `models/__init__.py`, `models/collection_connector.py`, `tests/__init__.py`, `tests/test_bejerman_connector.py`. Parent Seedian `pip.txt` `httpx` (task 1.1) and rebuilt image are outside this git.                              |

## Files Changed

| File                                                      | Action   | What Was Done                                                                   |
| --------------------------------------------------------- | -------- | ------------------------------------------------------------------------------- |
| `__init__.py`                                             | Created  | Import `models`; two-line AGPL header                                           |
| `__manifest__.py`                                         | Created  | AGPL-3, depends `collection`, not application, httpx extra, no hooks/data/menus |
| `LICENSE`                                                 | Created  | Copied verbatim from sqlite (read-only)                                         |
| `models/__init__.py`                                      | Created  | Import `collection_connector`                                                   |
| `models/collection_connector.py`                          | Created  | `_inherit` + `selection_add` `bejerman` + cascade                               |
| `tests/__init__.py`                                       | Created  | Import `test_bejerman_connector`                                                |
| `tests/test_bejerman_connector.py`                        | Created  | Selection + create + cascade + manifest depends                                 |
| `openspec/changes/bejerman-collection-connector/tasks.md` | Modified | Marked 1.2–1.4 `[x]`                                                            |

## Deviations from Design

None — implementation matches design. Manifest has no `data`/`views` yet (Phase 4). No
`post_init_hook`, sample data, MCP, menus, or `_bejerman_create_receipt`.

## Issues Found

- First `--mode=update` ran 0 tests because the addon was not installed. Init (`-i`) is
  required once; later GREEN used the assigned `--mode=update`.
- Image lacked `httpx` until `invoke img-build` (pip.txt already had it from 1.1).
  Install then failed with
  `Unable to install module "collection_connector_bejerman" because an external dependency is not met: httpx`.
- `load_manifest(...)` emits Odoo 19 `DeprecationWarning: Since 19.0, use Manifest`.
  Kept to mirror sqlite `test_sqlite_selection_add_and_path_field`.

## Remaining Tasks

Phase 2+ (not this batch):

- [ ] 2.1–2.4 Vendored SOAP + Cierre
- [ ] 3.1–3.5 Mapping and `_bejerman_*` read ops
- [ ] 4.1–4.3 Admin views and ACL
- [ ] 5.1–5.3 Docs, scoped pre-commit, full suite

## Workload / PR Boundary

- Mode: stacked PR slice (auto-chain, stacked-to-main)
- Current work unit: Phase 1 / PR 1 — httpx + scaffold + type
- Boundary: starts after 1.1 `httpx` in parent pip.txt; ends when type `bejerman` is
  selectable with uninstall cascade
- Estimated review budget impact: ~67 authored Python/manifest lines plus 661-line
  verbatim AGPL `LICENSE` copy (not logic). Under 400 authored-logic lines; LICENSE is
  the sqlite-required copy.

## Status

4/4 Phase 1 tasks complete. Ready for next apply batch (Phase 2).

---

# Phase 2: Vendored SOAP + Cierre

**Change**: bejerman-collection-connector **Mode**: Strict TDD **Work unit**: Phase 2
(PR 2 vendored SOAP + always-Cierre) — tasks 2.1–2.4 **Delivery**: auto-chain,
stacked-to-main **Attempt token**:
sha256:301a0d92858686b8d3341633b6487856d2129e5a04ddf7b03576e4324bd2d351 **Updated**:
2026-09-16

## Completed Tasks

- [x] 2.1 Vendor `service/{__init__,errors,soap,settings,session}.py`: record `Settings`
      / `Credentials`; one `allow_insecure` (HTTP + skip TLS unless CA path); no
      dotenv/CLI/`from_env`/Stock.
- [x] 2.2 `service/tablas.py` (`ObtenerClientes` only) and `service/queries.py`
      (`ObtenerJsonQueryVista` only).
- [x] 2.3 RED: `test_session_cierre_on_ejecutar_failure`.
- [x] 2.4 GREEN: `__exit__` always POSTs Cierre after Ejecutar fail; DEBUG SOAP logs use
      `redact_soap`; `BejermanError` never quotes `ErrorMsg`.

## TDD Cycle Evidence

| Task | Test File                                      | Layer                              | Safety Net               | RED                                                                                                                                                                                                                            | GREEN                                                              | TRIANGULATE                                                                                                                                               | REFACTOR                   |
| ---- | ---------------------------------------------- | ---------------------------------- | ------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------- |
| 2.1  | N/A (vendor)                                   | Structural                         | SDK read-only            | See 2.3 (missing `service` package)                                                                                                                                                                                            | See 2.4                                                            | ➖ Record Settings + single insecure flag; no env/CLI/Stock                                                                                               | ➖ None needed             |
| 2.2  | exercised via `tablas.obtener_clientes` in 2.3 | Structural                         | SDK operations read-only | See 2.3                                                                                                                                                                                                                        | See 2.4                                                            | ➖ `ObtenerClientes` only; `ObtenerJsonQueryVista` present for Phase 3                                                                                    | ➖ None needed             |
| 2.3  | `tests/test_bejerman_connector.py`             | Integration (Odoo TransactionCase) | N/A (new client)         | ✅ `ModuleNotFoundError: No module named 'odoo.addons.collection_connector_bejerman.service'` — `invoke test -m collection_connector_bejerman --mode=update` → `0 failed, 1 error(s) of 2 tests`; Phase 1 method still started | See 2.4                                                            | ✅ Cierre SOAPAction+body after fail **and** Token/xClave/ErrorMsg/URL absent from logs+exception; mock sequence Registro OK → Ejecutar ErrorMsg → Cierre | ➖ None needed             |
| 2.4  | same                                           | Integration                        | 2.3                      | Inherited from 2.3                                                                                                                                                                                                             | ✅ `0 failed, 0 error(s) of 2 tests when loading database 'devel'` | ✅ Same two independent assertion groups                                                                                                                  | ➖ None needed after GREEN |

### Test Summary

- **Total tests written (this batch)**: 1 (`test_session_cierre_on_ejecutar_failure`)
- **Total tests passing**: 2 (`test_bejerman_selection_add_and_cascade` + Cierre)
- **Layers used**: Unit (0), Integration (2), E2E (0)
- **Approval tests** (refactoring): None
- **Pure functions created**: SOAP builders/parse/`redact_soap`; Settings validation

## Work Unit Evidence

| Evidence                              | Required value                                                                                                                                                                                                                                                                                                                                               |
| ------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Focused test command and exact result | From Seedian root `/home/crisd/projects/seedian/seedian`: `invoke test -m collection_connector_bejerman --mode=update` → exit 0; `0 failed, 0 error(s) of 2 tests when loading database 'devel'`; both `Starting TestBejermanConnector.test_bejerman_selection_add_and_cascade` and `Starting TestBejermanConnector.test_session_cierre_on_ejecutar_failure` |
| RED evidence                          | Same command, before `service/`: exit 1; `ERROR: TestBejermanConnector.test_session_cierre_on_ejecutar_failure`; `ModuleNotFoundError: No module named 'odoo.addons.collection_connector_bejerman.service'`; `Module collection_connector_bejerman: 0 failures, 1 errors of 2 tests`; `0 failed, 1 error(s) of 2 tests when loading database 'devel'`        |
| GREEN evidence                        | After vendoring: exit 0; `0 failed, 0 error(s) of 2 tests when loading database 'devel'`                                                                                                                                                                                                                                                                     |
| Runtime harness                       | Stack already up (`seedian-odoo-1`, `seedian-db-1`). `--mode=update` sufficient (module installed in Phase 1). No `invoke start`, no `img-build`. Mock is `unittest.mock.patch` of `collection_connector_bejerman.service.session.httpx.Client.post`.                                                                                                        |
| Rollback boundary                     | Addon git `service/*.py` + `tests/test_bejerman_connector.py`. No parent `pip.txt` / Copier / collection / sqlite / SDK edits.                                                                                                                                                                                                                               |

## Files Changed

| File                                                      | Action   | What Was Done                                                                                                     |
| --------------------------------------------------------- | -------- | ----------------------------------------------------------------------------------------------------------------- |
| `service/__init__.py`                                     | Created  | Re-export client, Settings, errors                                                                                |
| `service/errors.py`                                       | Created  | `BejermanError` without `ErrorMsg` in `str()`                                                                     |
| `service/settings.py`                                     | Created  | Dataclass Settings/Credentials; `allow_insecure`; no dotenv                                                       |
| `service/soap.py`                                         | Created  | Trimmed SDK envelopes, parse, `redact_soap`; SOAP Fault does not quote faultstring                                |
| `service/session.py`                                      | Created  | `__exit__` always POSTs Cierre when token set; DEBUG redacted SOAP; generic transport errors; no Stock/`from_env` |
| `service/tablas.py`                                       | Created  | `ObtenerClientes` only                                                                                            |
| `service/queries.py`                                      | Created  | `ObtenerJsonQueryVista` only                                                                                      |
| `tests/test_bejerman_connector.py`                        | Modified | Added Cierre/redaction TransactionCase; patch `httpx.Client.post`                                                 |
| `openspec/changes/bejerman-collection-connector/tasks.md` | Modified | Marked 2.1–2.4 `[x]`                                                                                              |

## Cierre-always and redaction (how)

- After Registro stores `_token`, `__exit__` always calls `_post_cierre()` when
  `_token is not None`, including when `execute` raised (`_raise_if_not_ok` on Ejecutar
  ErrorMsg). Cierre SOAPAction is `EFlexSDK_WSCierreProceso`; body reuses the in-memory
  token.
- Request envelopes are logged at DEBUG only through `redact_soap` (Token/xClave element
  text → `***`, plus literal clave replace). Cierre unwind logs a fixed warning string
  (no `logger.exception` traceback).
- `_raise_if_not_ok` raises `BejermanError("Bejerman WS error")` and never interpolates
  `result.error_msg`. SOAP Fault raises `"SOAP Fault"` without `faultstring`.

## Deviations from Design

- Settings field name is `allow_insecure` (one flag) rather than SDK
  `BEJERMAN_ALLOW_INSECURE_HTTP` + `BEJERMAN_ALLOW_INSECURE_TLS`; maps to connector
  `bejerman_allow_insecure` in Phase 3.
- SOAP request logging is always DEBUG + redacted (no `BEJERMAN_LOG_SOAP` env), so the
  Cierre test can assert Token/xClave redaction without dotenv.
- `BejermanError` dropped the `error_msg=` constructor argument so it cannot leak via
  `str()` / chained logs.
- `service/queries.py` is unused by the Phase 2 test (required by 2.2; used in Phase 3).
- Test imports `service` inside the method so Phase 1 still loads if the package is
  missing.

## Issues Found

- None on harness this batch. Docker stack was already up; httpx already in the image
  from Phase 1. No rebuild.
- `load_manifest(...)` still emits Odoo 19
  `DeprecationWarning: Since 19.0, use Manifest` (Phase 1 sqlite mirror; unchanged).

## Remaining Tasks

Phase 3+ (not this batch):

- [ ] 3.1–3.5 Mapping and `_bejerman_*` read ops
- [ ] 4.1–4.3 Admin views and ACL
- [ ] 5.1–5.3 Docs, scoped pre-commit, full suite

## Workload / PR Boundary

- Mode: stacked PR slice (auto-chain, stacked-to-main)
- Current work unit: Phase 2 / PR 2 — vendored SOAP + Cierre
- Boundary: starts after type `bejerman` is selectable; ends when session always Cierre
  on Ejecutar fail with redacted logs
- Estimated review budget impact: ~785 lines across `service/*.py` + expanded tests
  (under 1200 attempt cap). Authored SOAP is a trimmed vendor copy, not a second SDK.

## Status

4/4 Phase 2 tasks complete. Ready for next apply batch (Phase 3).

---

# Phase 3: Mapping + four read ops

**Change**: bejerman-collection-connector **Mode**: Strict TDD **Work unit**: Phase 3
(PR 3 mapping + `_bejerman_*` reads) — tasks 3.1–3.5 **Delivery**: auto-chain,
stacked-to-main **Attempt token**:
sha256:8058650c24d4b1c0fe0e9ac12a380f35545ba74644fcd250cbbf1eebe8bf85af **Updated**:
2026-09-16

## Completed Tasks

- [x] 3.1 `service/mapping.py` plus
      `test_mapping_value_by_suffix_trim_cuit_kind_outstanding`: suffix map, trim pad
      (keep `"0"`), CUIT `XX-XXXXXXXX-X`, FC→invoice, quotation set, outstanding-only.
- [x] 3.2 `test_four_ops_return_sqlite_raw_shapes`,
      `test_create_receipt_unavailable_no_post`.
- [x] 3.3 `test_connection_probe_then_cierre`,
      `test_missing_obtener_clientes_or_view_fail_closed`.
- [x] 3.4 seller/customer/debt mapping tests, prefix-free ids, company isolation.
- [x] 3.5 `@api.private` `_bejerman_test_connection`, `_bejerman_list_sellers`,
      `_bejerman_list_customers`, `_bejerman_get_customer_debt` plus config fields. No
      `_bejerman_create_receipt`. Settings from `self`. Faults →
      `_bejerman_misconfigured()`.

## TDD Cycle Evidence

| Task    | Test File                                           | Layer                              | Safety Net             | RED                                                                                                                                                                                                                                | GREEN                                                                                                                             | TRIANGULATE                                                                                                                                                               | REFACTOR                                                                      |
| ------- | --------------------------------------------------- | ---------------------------------- | ---------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------- |
| 3.1     | `tests/test_bejerman_connector.py` `test_mapping_*` | Unit (imported in TransactionCase) | N/A (new mapping)      | ✅ Mapping tests written against the specified `value_by_suffix` / trim / CUIT / kind / outstanding API                                                                                                                            | ✅ `test_mapping_value_by_suffix_trim_cuit_kind_outstanding` passed on the ops-RED run (mapping module present; model fields not) | ✅ suffix hit vs miss; trim `"000E"` vs keep `"0"`; FC vs NP/PR; open vs paid/zero                                                                                        | ➖ None after GREEN                                                           |
| 3.2–3.4 | same                                                | Integration (Odoo TransactionCase) | mapping + Phase 2 SOAP | ✅ `invoke test -m collection_connector_bejerman --mode=update` → `0 failed, 10 error(s) of 13 tests`; `ValueError: Invalid field 'bejerman_ws_url' in 'collection.connector'` on every op test; Phase 1–2 + mapping still started | See 3.5                                                                                                                           | ✅ Each named test has two independent facts (dispatch vs `_bejerman_*`; ObtenerClientes vs view miss; dashed vs padded seller; unknown vs other-seller; A URL vs B rows) | ➖ Company-B fixture switched to SQL clone of `env.company` (account columns) |
| 3.5     | same                                                | Integration                        | 3.2–3.4                | Inherited from 3.2–3.4                                                                                                                                                                                                             | ✅ `0 failed, 0 error(s) of 13 tests when loading database 'devel'`                                                               | ✅ Four raw shapes + omitted `create_receipt` + probe/Cierre + isolation                                                                                                  | ➖ `_bejerman_call` wraps try/except; no behavior change                      |

### Test Summary

- **Total tests written (this batch)**: 11 (`test_mapping_*` + 10 named 3.2–3.4 methods)
- **Total tests passing**: 13 (Phase 1 selection + Phase 2 Cierre + 11 Phase 3)
- **Layers used**: Unit (1 mapping), Integration (12), E2E (0)
- **Approval tests** (refactoring): none beyond the company-create fixture
- **Pure functions created**: `value_by_suffix`, `trim_code`, `canonicalize_cuit`,
  `document_kind`, `is_outstanding`, `map_sellers` / `map_customers` /
  `map_customer_debt`

## Work Unit Evidence

| Evidence                              | Required value                                                                                                                                                                                                                                                                                          |
| ------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Focused test command and exact result | From Seedian root `/home/crisd/projects/seedian/seedian`: `invoke test -m collection_connector_bejerman --mode=update` → exit 0; `0 failed, 0 error(s) of 13 tests when loading database 'devel'`                                                                                                       |
| RED evidence                          | Same command after 3.2–3.4 tests + `mapping.py`, before model fields/ops: exit 1; `Module collection_connector_bejerman: 0 failures, 10 errors of 13 tests`; `0 failed, 10 error(s) of 13 tests when loading database 'devel'`; `ValueError: Invalid field 'bejerman_ws_url' in 'collection.connector'` |
| GREEN evidence                        | After 3.5 fields + `_bejerman_*`: exit 0; `0 failed, 0 error(s) of 13 tests when loading database 'devel'`                                                                                                                                                                                              |
| Runtime harness                       | Stack already up (`seedian-odoo-1`, `seedian-db-1`). `--mode=update` (`-u`) sufficient; new columns created. No `invoke start`, no `img-build`. Mock is `unittest.mock.patch` of `collection_connector_bejerman.service.session.httpx.Client.post`.                                                     |
| Rollback boundary                     | Addon git `service/mapping.py`, `models/collection_connector.py`, `tests/test_bejerman_connector.py`. No parent `pip.txt` / Copier / collection / sqlite / SDK / views / ACL.                                                                                                                           |

## Files Changed

| File                                                      | Action   | What Was Done                                                                                                                              |
| --------------------------------------------------------- | -------- | ------------------------------------------------------------------------------------------------------------------------------------------ |
| `service/mapping.py`                                      | Created  | Suffix map, trim, CUIT, kind, outstanding; sqlite-raw sellers/customers/debt                                                               |
| `models/collection_connector.py`                          | Modified | Config fields (no `groups` yet); `@api.private` four reads; `_bejerman_misconfigured`; Settings from `self`; no `_bejerman_create_receipt` |
| `tests/test_bejerman_connector.py`                        | Modified | Mapping unit assertions + 3.2–3.4 SOAP-mocked TransactionCase tests                                                                        |
| `openspec/changes/bejerman-collection-connector/tasks.md` | Modified | Marked 3.1–3.5 `[x]`                                                                                                                       |

## create_receipt fail-closed and isolation (how)

- There is no `_bejerman_create_receipt`. `_dispatch("create_receipt")` and
  `create_receipt({})` hit the collection dispatcher miss and raise
  `The requested connector operation is not available.` `httpx.Client.post` is never
  called (`assert_not_called`).
- Isolation: each connector builds `Settings`/`Credentials` from **its** fields. Company
  A’s posts go only to A’s `bejerman_ws_url`; A’s mapped seller ids do not include B’s
  rows. Mock routes payloads by POST URL.

## Deviations from Design

- Credential fields do **not** yet have `groups="base.group_system"` (task 4.3).
- Company B in `test_company_a_does_not_read_company_b` is inserted with SQL that copies
  `fiscalyear_*` / account columns from `env.company` (same pattern as `collection`
  customer-binding tests). ORM `res.company.create` on this devel DB omits those NOT
  NULL columns because `account` fields are not in the create defaults here.
- `_bejerman_call` is a private helper around the four ops so Registro/Cierre +
  Bejerman/TypeError/ValueError → generic UserError stay in one place.
- Mapping tests live in the same TransactionCase file (Odoo runner is the harness), not
  a pytest-only module.
- `test_errors_no_leak` / `test_admin_only_credentials_and_button` / views.xml are Phase
  4 — not added. Fail-closed UserErrors already omit ErrorMsg, URL, Token, clave, view
  names, SQL.

## Issues Found

- First GREEN attempt: 12/13; isolation failed creating company B (`autopost_bills` then
  `fiscalyear_last_day` NOT NULL). Fixed with SQL clone; re-run 13/13.
- Docker stack was already up; httpx already in the image. No rebuild.
- `load_manifest(...)` still emits Odoo 19
  `DeprecationWarning: Since 19.0, use Manifest` (Phase 1 sqlite mirror; unchanged).

## Remaining Tasks

Phase 4+ (not this batch):

- [ ] 4.1–4.3 Admin views and ACL
- [ ] 5.1–5.3 Docs, scoped pre-commit, full suite

## Workload / PR Boundary

- Mode: stacked PR slice (auto-chain, stacked-to-main)
- Current work unit: Phase 3 / PR 3 — mapping + four read ops
- Boundary: starts after SOAP Cierre; ends when four sqlite-raw reads work,
  `create_receipt` is unavailable, probes Cierre, isolation holds
- Estimated review budget impact: `mapping.py` (~272) + model (~120 net) + tests (~600
  added). Under the 1500 attempt cap. No views.

## Status

5/5 Phase 3 tasks complete. Ready for next apply batch (Phase 4).

---

# Phase 4: Admin form + ACL

**Change**: bejerman-collection-connector **Mode**: Strict TDD **Work unit**: Phase 4
(PR 4 admin views + ACL) — tasks 4.1–4.3 **Delivery**: auto-chain, stacked-to-main
**Attempt token**:
sha256:e12ee8edc40cf36191b78120ed32124beb1583f69d7a075ef677eef97f814439 **Updated**:
2026-09-16

## Completed Tasks

- [x] 4.1 RED: `test_admin_only_credentials_and_button`, `test_errors_no_leak` with
      `_LEAK_TOKENS` (URL, user, clave, Token, SOAP tags, view names, SQL, ErrorMsg).
- [x] 4.2 GREEN: `views/collection_connector_views.xml` inherits
      `collection.view_collection_connector_form`; type-gated fields; clave
      `password="True"`; Test Connection `groups="base.group_system"`. Manifest `data`
      is that view only — no menus, MCP, hooks, sample data, or ACL CSV.
- [x] 4.3 GREEN: all credential/config fields `groups="base.group_system"`; UserError
      stays `_NOT_CONFIGURED` and omits `_LEAK_TOKENS`.

## TDD Cycle Evidence

| Task | Test File                          | Layer                              | Safety Net  | RED                                                                                                                                                                                                                                                                                                                                  | GREEN                                                               | TRIANGULATE                                                                                                                                                           | REFACTOR                                                                                          |
| ---- | ---------------------------------- | ---------------------------------- | ----------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------- |
| 4.1  | `tests/test_bejerman_connector.py` | Integration (Odoo TransactionCase) | Phase 3 ops | ✅ `invoke test -m collection_connector_bejerman --mode=update` → `1 failed, 0 error(s) of 15 tests`; `test_admin_only_credentials_and_button` `AssertionError: 'base.group_system' not found in set()` for `bejerman_ws_url`. `test_errors_no_leak` already passed (Phase 3 `_bejerman_misconfigured()`). Existing 13 still started | See 4.2–4.3                                                         | ✅ Admin vs internal `fields_get`/`get_view`/`read`; password on clave; ObtenerClientes ErrorMsg, missing views, Registro fail, HTTP URL, mocked `httpx.ConnectError` | User fixture: `new_test_user` hit `autopost_bills` NOT NULL; replaced with SQL/ORM partner helper |
| 4.2  | same + views XML                   | Integration                        | 4.1         | Inherited (xmlid/arch missing until view loaded)                                                                                                                                                                                                                                                                                     | ✅ Combined inherit + `get_view` as Settings vs `group_user`        | ✅ Button `invisible="type != 'bejerman'"` + `groups="base.group_system"`; all config fields after `type`                                                             | ➖ None after GREEN                                                                               |
| 4.3  | same                               | Integration                        | 4.1–4.2     | Inherited (field `groups` empty)                                                                                                                                                                                                                                                                                                     | ✅ `0 failed, 0 error(s) of 15 tests when loading database 'devel'` | ✅ Python `groups` + AccessError on credential `read` for internal; leak tokens on UserError                                                                          | ➖ Dropped Python `password=True` (Odoo 19 Char has no such parameter; mask is the view widget)   |

### Test Summary

- **Total tests written (this batch)**: 2 (`test_admin_only_credentials_and_button`,
  `test_errors_no_leak`)
- **Total tests passing**: 15 (13 prior + 2 Phase 4)
- **Layers used**: Unit (1 mapping, unchanged), Integration (14), E2E (0)
- **Approval tests** (refactoring): user-create fixture only
- **Pure functions created**: none

## Work Unit Evidence

| Evidence                              | Required value                                                                                                                                                                                                                                                                                                            |
| ------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Focused test command and exact result | From Seedian root `/home/crisd/projects/seedian/seedian`: `invoke test -m collection_connector_bejerman --mode=update` → exit 0; `0 failed, 0 error(s) of 15 tests when loading database 'devel'`                                                                                                                         |
| RED evidence                          | Same command after 4.1 tests, before views/groups: exit 1; `Module collection_connector_bejerman: 1 failures, 0 errors of 15 tests`; `1 failed, 0 error(s) of 15 tests when loading database 'devel'`; `AssertionError: 'base.group_system' not found in set() : bejerman_ws_url must be restricted to base.group_system` |
| GREEN evidence                        | After 4.2 view + 4.3 field groups: exit 0; `0 failed, 0 error(s) of 15 tests when loading database 'devel'`; both new methods started                                                                                                                                                                                     |
| Runtime harness                       | Stack already up (`seedian-odoo-1`, `seedian-db-1`). `--mode=update` (`-u`) loaded the new XML. No `invoke start`, no `img-build`.                                                                                                                                                                                        |
| Rollback boundary                     | Addon git `views/collection_connector_views.xml`, `__manifest__.py` `data`, `models/collection_connector.py` field `groups`, `tests/test_bejerman_connector.py`. No parent `pip.txt` / Copier / collection / sqlite / SDK / menus / ACL CSV / README.                                                                     |

## Files Changed

| File                                                      | Action   | What Was Done                                                                                               |
| --------------------------------------------------------- | -------- | ----------------------------------------------------------------------------------------------------------- |
| `tests/test_bejerman_connector.py`                        | Modified | `_LEAK_TOKENS`; admin vs internal form/fields/read; SOAP/view/credential leak cases                         |
| `views/collection_connector_views.xml`                    | Created  | Inherit collection form; type-gated fields; password on clave; Test Connection `groups="base.group_system"` |
| `__manifest__.py`                                         | Modified | `"data": ["views/collection_connector_views.xml"]` only                                                     |
| `models/collection_connector.py`                          | Modified | All Bejerman config fields `groups="base.group_system"`                                                     |
| `openspec/changes/bejerman-collection-connector/tasks.md` | Modified | Marked 4.1–4.3 `[x]`                                                                                        |

## Admin-only and leak-free (how)

- **Admin-only:** Python `groups="base.group_system"` on every Bejerman config field so
  `fields_get` / `read` / combined `get_view` omit them for `base.group_user` without
  Settings. Inherit view adds the same fields after `type` with
  `invisible="type != 'bejerman'"` and a header Test Connection button with the same
  invisible expression plus `groups="base.group_system"`. Clave is masked with view
  `password="True"`. Collection ACL is unchanged (`group_user` read, `group_system`
  write); no extra groups, menus, or security CSV.
- **Leak-free:** SOAP ErrorMsg, missing Query views, failed Registro, HTTP URL without
  `allow_insecure`, and `httpx.ConnectError` whose message quotes
  URL/user/clave/Token/ErrorMsg all become
  `UserError("The collection connector is not configured.")`. `_LEAK_TOKENS` (fixture
  ErrorMsg, Token, URL, usuario, clave, SOAP tags, view names, SQL) are asserted absent
  from that string. Public `test_connection()` / `list_sellers()` raise the same
  UserError, so MCP-visible text is the same generic sentence.

## Deviations from Design

- Odoo 19 `fields.Char` has no `password` parameter (`Field` warns on unknown kwargs).
  Masking is the form `password="True"` widget, not a Python field flag.
- `test_errors_no_leak` was already GREEN on the 4.1 RED run: Phase 3
  `_bejerman_misconfigured()` already omitted internals. The RED failure for this batch
  was `test_admin_only_credentials_and_button` only.
- Admin/internal users are created with the collection ACL `autopost_bills` partner
  pattern (`new_test_user` omitted the NOT NULL column on this devel DB).
- XML field nodes also set `groups="base.group_system"` in addition to the Python field
  groups (button groups are XML-only).

## Issues Found

- First GREEN attempt: 0 failed, 1 error of 15 — `new_test_user` INSERT into
  `res_partner` omitted `autopost_bills`. Replaced with `_create_user`; re-run 15/15.
- Docker stack was already up; httpx already in the image. No rebuild. `-u` via
  `invoke test --mode=update` loaded the new XML.
- `load_manifest(...)` still emits Odoo 19
  `DeprecationWarning: Since 19.0, use Manifest` (Phase 1 sqlite mirror; unchanged).

## Remaining Tasks

Phase 5 (not this batch):

- [ ] 5.1 Write `readme/DESCRIPTION.md` (OCA fragment only).
- [ ] 5.2
      `pre-commit run --files odoo/custom/src/private/collection_connector_bejerman/** odoo/custom/dependencies/pip.txt`.
- [ ] 5.3 `invoke test -m collection_connector_bejerman --mode=update` (mock httpx; live
      ERP is apply/smoke).

## Workload / PR Boundary

- Mode: stacked PR slice (auto-chain, stacked-to-main)
- Current work unit: Phase 4 / PR 4 — admin form + ACL
- Boundary: starts after four read ops; ends when Settings-only masked credentials and
  leak-free UserErrors are tested
- Estimated review budget impact: view XML (~95) + field groups (~40 net) + tests (~250
  added). Under the 800-line cap. No README (5.1).

## Status

3/3 Phase 4 tasks complete. Ready for next apply batch (Phase 5).

---

# Phase 5: Docs and quality

**Change**: bejerman-collection-connector
**Mode**: Strict TDD
**Work unit**: Phase 5 (PR 5 docs + lint + suite) — tasks 5.1–5.3
**Delivery**: auto-chain, stacked-to-main
**Attempt token**: sha256:8f34790a193b9d9928bf9d9a18427c881c5de745f5f519c3d21a72634a5d8d44
**Updated**: 2026-09-16

## Completed Tasks

- [x] 5.1 `readme/DESCRIPTION.md` (OCA fragment only). Sqlite tone; Bejerman facts.
- [x] 5.2 Scoped pre-commit from Seedian root; lint clean on addon source + `pip.txt`.
- [x] 5.3 `invoke test -m collection_connector_bejerman --mode=update` — 15/15 green (mock httpx).

## TDD Cycle Evidence

| Task | Test File | Layer | Safety Net | RED | GREEN | TRIANGULATE | REFACTOR |
|------|-----------|-------|------------|-----|-------|-------------|----------|
| 5.1 | N/A (OCA fragment) | Structural | sqlite DESCRIPTION (read-only) | ➖ Docs fragment | ✅ Generated `README.rst` via `oca-gen-addon-readme` | ➖ One fragment, sqlite tone | Prettier wrapped DESCRIPTION.md |
| 5.2 | N/A (lint) | Structural | Seedian pre-commit | ✅ First pass failed: ruff 1 auto-fix; prettier `state.yaml` duplicate keys; pylint_odoo W8113 redundant `string=`; EOF on `pip.txt`; optional missing README | ✅ Second pass on addon source + `pip.txt` (openspec excluded): all applicable hooks Passed | ➖ | Dropped redundant field `string=` (labels unchanged) |
| 5.3 | `tests/test_bejerman_connector.py` | Integration | 15 prior tests | ➖ No new tests | ✅ `0 failed, 0 error(s) of 15 tests when loading database 'devel'` | ➖ Confirmation suite | ➖ None |

### Test Summary

- **Total tests written (this batch)**: 0
- **Total tests passing**: 15 (unchanged)
- **Layers used**: Unit (1 mapping), Integration (14), E2E (0)
- **Approval tests** (refactoring): none
- **Pure functions created**: none

## Work Unit Evidence

| Evidence | Required value |
|---|---|
| Focused test command and exact result | From Seedian root `/home/crisd/projects/seedian/seedian`: `invoke test -m collection_connector_bejerman --mode=update` → exit 0; `0 failed, 0 error(s) of 15 tests when loading database 'devel'` |
| Pre-commit (clean) | Explicit `--files` listing addon source + generated README + `pip.txt` (21 files; no `.git`, `__pycache__`, or `openspec/`). Exit 0. All applicable hooks Passed. Optional pylint C8101 wants author `Eynes` (sqlite same; `--exit-zero`). |
| Runtime harness | Stack already up (`seedian-odoo-1`, `seedian-db-1`). `--mode=update` (`-u`) sufficient. No `invoke start`, no `img-build`. Mock is `unittest.mock.patch` of `httpx.Client.post`. No live ERP. |
| Rollback boundary | Addon git `readme/DESCRIPTION.md`, generated `README.rst` + `static/description/index.html`, `models/collection_connector.py` redundant-`string=` drop, parent `pip.txt` trailing newline. No Copier / collection / sqlite / SDK / httpx removal. |

## Files Changed

| File | Action | What Was Done |
|------|--------|---------------|
| `readme/DESCRIPTION.md` | Created | OCA fragment; sqlite tone; Bejerman facts |
| `README.rst` | Generated | `oca-gen-addon-readme` from the fragment (not hand-edited) |
| `static/description/index.html` | Generated | `oca-gen-addon-readme --gen-html` |
| `models/collection_connector.py` | Modified | Removed W8113-redundant `string=` on six fields |
| `odoo/custom/dependencies/pip.txt` | Modified | Trailing newline only; `httpx` kept |
| `openspec/changes/bejerman-collection-connector/tasks.md` | Modified | Marked 5.1–5.3 `[x]` |
| `openspec/changes/bejerman-collection-connector/apply-progress.md` | Modified | This Phase 5 section |

## Deviations from Design

- Assigned glob `collection_connector_bejerman/**` includes orchestrator `state.yaml` with duplicate `delivery_strategy` / `updated` / `artifacts` keys. Prettier aborts (`SyntaxError: Map keys must be unique`). Clean lint used explicit `--files` excluding `openspec/` so Phase 1–4 progress is not reflowed again.
- Nested addon git did **not** skip files when `--files` listed them from Seedian root.
- Optional pylint C8101 `manifest-required-author` Eynes: not changed (sqlite/Seedian author).
- Generated `static/description/index.html` is ~415 lines (Docutils CSS). Authored Phase 5 logic is the DESCRIPTION fragment + six dropped `string=` kwargs.

## Issues Found

- First pre-commit pass: ruff auto-fixed 1 issue; prettier failed on `state.yaml`; mandatory pylint W8113 on six field `string=` values equal to the auto title; EOF fixer added newline to parent `pip.txt`; optional `missing-readme` until `oca-gen-addon-readme` wrote `README.rst`.
- Docker stack was already up; httpx already in the image. No rebuild.
- `load_manifest(...)` still emits Odoo 19 `DeprecationWarning: Since 19.0, use Manifest` (Phase 1 sqlite mirror; unchanged).

## Remaining Tasks

None. All 19 tasks `[x]`. Live ERP smoke is apply/smoke, not this checkbox.

## Workload / PR Boundary

- Mode: stacked PR slice (auto-chain, stacked-to-main)
- Current work unit: Phase 5 / PR 5 — readme + lint + suite
- Boundary: starts after admin form + ACL; ends when DESCRIPTION fragment, scoped pre-commit, and 15 mock tests are green
- Estimated review budget impact: DESCRIPTION (~15) + generated README (~59) + generated index.html (~415) + six `string=` drops. Under 800 authored lines; index.html is hook output.

## Status

3/3 Phase 5 tasks complete. All 19 change tasks `[x]`. Do not commit. Ready for verify / live ERP smoke (not this batch).
