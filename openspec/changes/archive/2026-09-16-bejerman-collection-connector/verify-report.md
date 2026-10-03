```yaml
schema: gentle-ai.verify-result/v1
evidence_revision: sha256:74867fbf89d842ff12b060c86e2f96ef7144fade8b2c1e837bea4cf4a1179b86
verdict: pass
blockers: 0
critical_findings: 0
requirements: 12/12
scenarios: 13/13
test_command: invoke test -m collection_connector_bejerman --mode=update
test_exit_code: 0
test_output_hash: sha256:aa2bb7e18db1e6803160f2c14a3492a70a84fdd2e14ae4cc03004d07351a971b
build_command: invoke img-build
build_exit_code: 0
build_output_hash: sha256:68a8ffcb557f14b7099cb0eeb4f31a9b26e77e82a00002ee2c634e3036f03e5b
```

## Verification Report

**Change**: bejerman-collection-connector
**Version**: 19.0.1.0.0
**Mode**: Strict TDD

### Completeness
| Metric | Value |
|--------|-------|
| Tasks total | 19 |
| Tasks complete | 19 |
| Tasks incomplete | 0 |

All `tasks.md` checkboxes are `[x]`. `apply-progress.md` records Phases 1–5 complete. Live ERP smoke is an apply/smoke gate and is not a verify task.

### Build & Tests Execution
**Build**: ✅ Passed
```text
invoke img-build
exit 0
[+] Building 71.1s (12/12) FINISHED
✔ Image registry.eynes.com.ar/seedian/seedian:master-latest Built 71.1s
build_output_hash: sha256:68a8ffcb557f14b7099cb0eeb4f31a9b26e77e82a00002ee2c634e3036f03e5b
```

**Tests**: ✅ 15 passed / ❌ 0 failed / ⚠️ 0 skipped
```text
invoke test -m collection_connector_bejerman --mode=update
cwd: /home/crisd/projects/seedian/seedian
exit 0
odoo.tests.result: 0 failed, 0 error(s) of 15 tests when loading database 'devel'
seedian-odoo-1 stack was already up; runner used a doodba odoo-run container.
All 15 TestBejermanConnector methods started and finished without FAIL/ERROR.
test_output_hash: sha256:aa2bb7e18db1e6803160f2c14a3492a70a84fdd2e14ae4cc03004d07351a971b
```

**Coverage**: ➖ Not available / threshold: 0% → skipped (Odoo native runner has no coverage tool)

**Lint (quality, not a test substitute)**: scoped `pre-commit --files` on 20 addon source files plus `odoo/custom/dependencies/pip.txt`, excluding `openspec/` (prettier cannot parse duplicate keys in `state.yaml`). Exit 0. Mandatory hooks Passed. Optional pylint C8101 (`manifest-required-author` wants `Eynes`) printed and did not fail the hook.

### Spec Compliance Matrix
| Requirement | Scenario | Test | Result |
|-------------|----------|------|--------|
| Type registration | Type is selectable | `tests/test_bejerman_connector.py` > `test_bejerman_selection_add_and_cascade` | ✅ COMPLIANT |
| Raw read operations | Four ops return raw rows | `tests/test_bejerman_connector.py` > `test_four_ops_return_sqlite_raw_shapes` | ✅ COMPLIANT |
| Receipt write unavailable | create_receipt fails closed | `tests/test_bejerman_connector.py` > `test_create_receipt_unavailable_no_post` | ✅ COMPLIANT |
| Test Connection | Full probe then close | `tests/test_bejerman_connector.py` > `test_connection_probe_then_cierre` | ✅ COMPLIANT |
| Seller mapping | Seller suffix map | `tests/test_bejerman_connector.py` > `test_list_sellers_suffix_trim_zero_commission` | ✅ COMPLIANT |
| Seller-scoped customers | Seller-scoped canonical customers | `tests/test_bejerman_connector.py` > `test_list_customers_seller_scope_cuit` | ✅ COMPLIANT |
| Debt mapping | Kind and outstanding | `tests/test_bejerman_connector.py` > `test_get_customer_debt_kind_outstanding` | ✅ COMPLIANT |
| Debt mapping | Unknown customer | `tests/test_bejerman_connector.py` > `test_get_customer_debt_unknown_empty` | ✅ COMPLIANT |
| Prefix-free identifiers | Prefixes stripped | `tests/test_bejerman_connector.py` > `test_emitted_ids_omit_query_prefixes` | ✅ COMPLIANT |
| No leakage | Errors hide internals | `tests/test_bejerman_connector.py` > `test_errors_no_leak` | ✅ COMPLIANT |
| Admin-only credentials | Admin-only masked credentials | `tests/test_bejerman_connector.py` > `test_admin_only_credentials_and_button` | ✅ COMPLIANT |
| Company isolation | Isolation | `tests/test_bejerman_connector.py` > `test_company_a_does_not_read_company_b` | ✅ COMPLIANT |
| Missing ERP grants | Missing grants fail closed | `tests/test_bejerman_connector.py` > `test_missing_obtener_clientes_or_view_fail_closed` | ✅ COMPLIANT |

**Compliance summary**: 13/13 scenarios compliant (each covering test passed in this verify run). Extra lifecycle coverage: `test_session_cierre_on_ejecutar_failure` and mapping unit `test_mapping_value_by_suffix_trim_cuit_kind_outstanding` also passed. Absence of `_bejerman_create_receipt` is specified and asserted.

### Correctness (Static Evidence)
| Requirement | Status | Notes |
|------------|--------|-------|
| Type registration | ✅ Implemented | `_inherit` `collection.connector`; `selection_add` `bejerman`; `ondelete={'bejerman': 'cascade'}`. Test asserts selectable type, cascade registry, and `depends: collection`; it does not perform a live uninstall. |
| Raw read operations | ✅ Implemented | `@api.private` `_bejerman_test_connection`, `_bejerman_list_sellers`, `_bejerman_list_customers`, `_bejerman_get_customer_debt` return sqlite-raw keys without MCP `source`. |
| Receipt write unavailable | ✅ Implemented | No `_bejerman_create_receipt`. Dispatcher/`create_receipt` raise generic unavailable `UserError`; httpx is not POSTed. |
| Test Connection | ✅ Implemented | Probe is Registro → ObtenerClientes → seller Query → debt Query; `BejermanClient.__exit__` always POSTs Cierre when a token exists. |
| Seller mapping | ✅ Implemented | `mapping.map_sellers`: suffix keys, trim pad (keep `"0"`), drop inactive, commission 0–100 inclusive. |
| Seller-scoped customers | ✅ Implemented | `map_customers` filters seller + active; CUIT canonical `XX-XXXXXXXX-X` on rows and lookup. |
| Debt mapping | ✅ Implemented | FC-style → invoice; configured NP/PR → quotation; else invoice; outstanding `balance > 0` and `open`/`overdue`; unknown/inactive/other-seller → `{customer: None, invoices: []}`. |
| Prefix-free identifiers | ✅ Implemented | Emitted ids/codes use suffix map + trim; prefix blob asserted absent. |
| No leakage | ✅ Implemented | Faults become `_bejerman_misconfigured()` (`The collection connector is not configured.`). SOAP Fault/`ErrorMsg` are not interpolated; logs use `redact_soap`. |
| Admin-only credentials | ✅ Implemented | All config fields `groups="base.group_system"`; inherit `collection.view_collection_connector_form`; clave `password="True"`; Test Connection `groups="base.group_system"`. Manifest `data` is the view only; no menus, MCP, hooks, sample data, or ACL CSV. |
| Company isolation | ✅ Implemented | Settings/URL come from `self`; company A POSTs only to A's URL and does not receive B's seller rows. |
| Missing ERP grants | ✅ Implemented | Refused ObtenerClientes or Query view → generic `UserError`; Cierre still runs. |

### Coherence (Design)
| Decision | Followed? | Notes |
|----------|-----------|-------|
| Vendor SOAP (no pip SDK / dotenv / CLI / Stock) | ✅ Yes | `service/{errors,soap,settings,session,tablas,queries}.py`; `ObtenerClientes` and `ObtenerJsonQueryVista` only. |
| Omit `_bejerman_create_receipt` | ✅ Yes | Specified absence; fail closed via dispatcher. |
| Seedian-tracked files; no `git-init` | ✅ Yes | Apply did not `git-init`. A pre-existing addon `.git` is the SDD planning repo; production files live under Seedian `odoo/custom/src/private/`. |
| One `bejerman_allow_insecure` flag | ✅ Yes | HTTP allowed and TLS verify off unless CA path set. HTTPS default in `Settings`. |
| Query fetch then Python suffix-map | ✅ Yes | `value_by_suffix` + filter in `mapping.py`. |
| unittest.mock of `httpx.Client.post` | ✅ Yes | No pytest-httpx; no live ERP in this verify run. |
| Credential groups + password widget | ✅ Yes | Odoo 19 `fields.Char` has no `password` parameter; mask is the form widget, matching the documented apply deviation. |
| `httpx` in `pip.txt` + `external_dependencies` + img-build | ✅ Yes | `pip.txt` contains `httpx`; manifest extra present; this verify rebuilt the image successfully. |
| `_bejerman_call` wrapper | ✅ Yes | Documented helper; Bejerman/TypeError/ValueError → generic UserError. |

### TDD Compliance
| Check | Result | Details |
|-------|--------|---------|
| TDD Evidence reported | ✅ | Five TDD Cycle Evidence tables in `apply-progress.md` (Phases 1–5). |
| All tasks have tests | ✅ | 13/19 tasks have dedicated methods in `tests/test_bejerman_connector.py`. 6/19 are structural/docs/lint (1.1, 1.2, 2.1, 2.2, 5.1, 5.2) with N/A RED as allowed. |
| RED confirmed (tests exist) | ✅ | 13/13 RED-written tasks point at `tests/test_bejerman_connector.py`, which exists. |
| GREEN confirmed (tests pass) | ✅ | 15/15 methods passed in this run (`0 failed, 0 error(s) of 15 tests`). |
| Triangulation adequate | ✅ | Mapping, debt (kind vs unknown), probe vs missing grants, admin vs internal, A vs B URLs use distinct expected values. Structural tasks remain ➖. |
| Safety Net for modified files | ✅ | New addon files are N/A (new). Later phases re-ran the growing suite before modifying models/views/tests. |

**TDD Compliance**: 6/6 checks passed (19/19 tasks have complete TDD evidence in apply-progress; GREEN confirmed against this run)

### Test Layer Distribution
| Layer | Tests | Files | Tools |
|-------|-------|-------|-------|
| Unit | 1 | 1 | imported `mapping` inside Odoo TransactionCase |
| Integration | 14 | 1 | Odoo TransactionCase + `unittest.mock` of `httpx.Client.post` |
| E2E | 0 | 0 | not installed / live ERP is apply/smoke, not verify |
| **Total** | **15** | **1** | |

### Changed File Coverage
Coverage analysis skipped — no coverage tool detected

### Assertion Quality
**Assertion quality**: ✅ All assertions verify real behavior

Empty `{customer: None, invoices: []}` is paired with non-empty debt/customer tests. Admin field loops iterate a non-empty `_BEJERMAN_CONFIG_FIELDS` tuple. Leak checks iterate non-empty `_LEAK_TOKENS`. No tautologies, ghost loops, or production-free assertions found.

### Quality Metrics
**Linter**: ✅ No errors (optional C8101 author `Eynes` on `__manifest__.py`; hook exit 0; sqlite/Seedian author unchanged)
**Type Checker**: ➖ Not available

### Issues Found
**CRITICAL**: None
**WARNING**: None
**SUGGESTION**:
- Optional pylint C8101 wants manifest author `Eynes`; Seedian author matches sqlite and was left unchanged.
- `test_bejerman_selection_add_and_cascade` proves `ondelete` cascade registry rather than performing a live module uninstall.
- `_call_body` in the test helper has an unreachable `return str(content)` after decoding bytes (tests still pass because POST bodies are bytes).
- `load_manifest(...)` still emits Odoo 19 `DeprecationWarning: Since 19.0, use Manifest` (sqlite mirror).
- Live Bejerman ERP grants were not exercised (apply/smoke only; not a verify blocker).

### Verdict
PASS
All 19 tasks complete; 12/12 requirements and 13/13 scenarios have covering tests that passed; `invoke test` and `invoke img-build` both exited 0.
