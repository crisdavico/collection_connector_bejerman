# Bejerman open debt snapshot

## Objective

Let the collections agent read a customer's open balance (invoices and quotations) from
Bejerman through `collection.connector` `get_customer_debt`, using the Bejerman Queries
view `Saldos al día/*`.

## Problem

- `service/mapping.py` was written for synthetic aliases (`id`, `Saldo`, `customer_id`,
  `QDebt_*`). Real `Saldos al día` rows use `STA_COMPROBANTESVENTA_001*` keys, so every
  real row is dropped.
- The view has no server-side filter today. One full download is ~171k rows, ~200 MB, ~1
  minute. Calling it per `get_customer_debt` (agent, allocation revalidation, debt
  picker) is not viable.

## Why

Sellers need current customer debt in the agent; Odoo must not hit a 200 MB SOAP call
per question.

## Scope

- Only this addon (`collection_connector_bejerman`).
- Read-only against Bejerman. No receipt write-back.
- Out of scope / read-only: `collection/`, `collection_connector_sqlite/`, Bejerman SDK,
  Doodba `pip.txt`, nebula-agent.

## Decisions (user, 2026-10-03)

- Full batch for now; a filtered child view may be created next week.
- Keep only **open** debt (balance > 0). Reconciled rows are discarded.
- Negative balances (credit notes) are dropped (assumption stated, not contested).
- `CVETCO_COD == PRE` -> `quotation`; every other type -> `invoice`.
- Refresh cron every **4 hours**, plus a manual admin "Refresh debt" button.
- Amounts in local currency: `CVE_IMPMONLOC` / `CVE_SALDOMONLOC`.
- Disabled customers are not brought: neither the customer nor any of its debt is stored
  or served (user, 2026-10-03). This closes the earlier open question about the 71
  disabled customers with debt.

## Constraints

- `external_invoice_id` must be stable (reservations key on it):
  `CVETCO_COD|CVE_CODPVT|CVE_LETRA|CVE_NRO` (stripped).
- `state` is derived: `overdue` when `CVE_FVTO` < today (company tz), else `open`.
- Fail closed: a failed refresh keeps the previous snapshot; no credentials, token, URL
  or `ErrorMsg` in logs or user errors.
- Admin-only credentials and refresh button (`base.group_system`).
- Company isolation on the snapshot.

## Tasks

Route per task: delegated direct (writer trigger: 2+ non-trivial files).

- [x] T1 Measure peak memory and time of parsing the real full batch with the addon's
      `service/` code (outside Odoo, `.env` loaded but never printed). Decide: keep
      `parse_response` + `json.loads`, or stream.
- [x] T2 Rewrite mapping for real `STA_COMPROBANTESVENTA_001*` rows (id, number, dates,
      amounts, kind, customer code, seller code, open filter). Tests with real-shaped
      fixtures, RED first.
- [x] T3 Snapshot model `collection.connector.bejerman.debt` (+ customer cache from
      `ObtenerClientes`), ACL, atomic replace refresh, fail-closed.
- [x] T4 `ir.cron` every 4 hours + admin "Refresh debt" button + view fields (last
      refresh time / row count).
- [x] T5 `_bejerman_get_customer_debt` / `_bejerman_list_customers` read the snapshot;
      derive `state`; optional live path when a filtered view field is configured.
- [x] T7 Disabled customers are not brought: the refresh keeps only debt of the enabled
      customers being cached; the live filtered path cannot return a disabled customer's
      debt (tests, RED first).
- [x] T6 Manifest version bump, full module tests, scoped pre-commit, README / spec
      update.

## Acceptance criteria

- `get_customer_debt(seller, CUIT)` returns only positive-balance rows of that customer
  from the latest snapshot, `PRE` as `quotation`, others `invoice`, with stable ids, no
  SOAP call.
- Refresh failure leaves the previous snapshot and leaks nothing.
- Cron runs every 4 hours; button is admin-only.

## Checks

- TDD: strict (source: `openspec/config.yaml` `strict_tdd: true` and
  `collection/AGENTS.md`). Runner:
  `invoke test -m collection_connector_bejerman --mode=update` from Seedian root.
- Lint:
  `pre-commit run --files odoo/custom/src/private/collection_connector_bejerman/**`.

## Delivery

- Forecast: ~800 authored changed lines (above the ~400 budget). Strategy from
  `openspec/config.yaml`: `auto-chain`, `stacked-to-main`.
- Commits (user decision 2026-10-03): one initial commit on `main` with the whole addon.
  The pre-existing connector was never committed and its original bytes were not
  recoverable, so a separate baseline commit was impossible.
  - `8a179c6` feat(collection_connector_bejerman): add Bejerman connector with open debt
    snapshot (T1-T7).
- Before committing, the real customer code copied from the example row into
  `tests/test_bejerman_debt_mapping.py` was replaced with the synthetic `ZZ0001`.
- Lint at commit: repo-pinned `ruff@0.13.0 check` and `format --check` clean. The
  parent pre-commit no longer sees the addon's files once the nested repo has a HEAD.
- Native review: not run. `review assess` reports `unassessable` (a root commit has no
  base ref) and `review status --committed-only` requires `--base-ref`. Pending user
  decision.

## Progress

- 2026-10-03: plan approved; document created.
- 2026-10-03 T1 done (route: delegated direct writer; throwaway script in the session
  scratchpad, addon `service/` loaded through importlib, env loaded with python-dotenv,
  nothing sensitive printed). Observed on the real ERP, scenario `TEST`, view
  `Saldos al día/*`:
  - Fetch wall time 22.9-23.4 s (one `Ejecutar`, 199,929,826 chars of `DatosJSON`).
  - Peak RSS 736 MB right after fetch+`parse_response`; 801 MB at the end of the
    analysis (baseline 27 MB). The second decode (`json.loads` of the inner string) took
    0.5 s and did not raise the peak. Well below the 1.2 GB bar, so the current parse
    path is KEPT (no `iterparse`).
  - Rows 171,076; open (`CVE_SALDOMONLOC > 0`) 1,254; negative 131 (dropped). Open
    types: FHK 716, PRE 508, DHK 13, FMK 4, FEM 5, FEH 3, PRS 2, FIH 1, ND 1, DHS 1.
    Open currencies: `1` 1,246 rows, `2` 8 rows (amounts used are local-currency
    columns). 568 distinct customers with open debt; all 568 match a `Cliente_Codigo`
    after `trim_code`. All 1,254 composite ids unique.
  - Two real-ERP facts the old code got wrong (both now fixed with tests):
    1. Query views answer a **JSON string that holds the JSON rows**
       (`json.loads(DatosJSON)` returns `str`); the old path raised
       `TypeError("Bejerman payload is not a list")` so every real read was swallowed as
       "not configured". Fix: decode once in
       `QueriesOperations.obtener_json_query_vista`.
    2. `ObtenerClientes` with `ParametrosJson` `{}` answers `Resultado=ERR`; `[]` works
       (7,739 clients). Fix: `TablasOperations.obtener_clientes` sends `[]`.
  - Shape facts used by the mapping: `CVE_CODPVT` is 5 chars (`00004`) or blank;
    `CVE_LETRA` `A`/`B`/`E`/`D` or a single blank; `CVE_NRO` 8 chars;
    `CVE_FVTO`/`CVE_FEMISION` are `...T00:00:00.000Z` and never null on open rows;
    `Cliente_Habilitado` is a JSON bool (6,416 true / 1,323 false); 11-digit CUITs
    6,081, many 8-digit documents.
- 2026-10-03 T2 done. Mapping rewritten for real rows (`map_debt_row`, `map_open_debt`,
  `debt_state`, `entry_to_invoice`, `map_customer_rows`, `map_customer_debt` now takes
  `today`); synthetic `QDebt_*` fixtures replaced by real-shaped `_debt_row(...)`
  fixtures. Keys resolve by exact alias suffix once per row shape; an alias matching 2+
  keys fails the row closed.

  - RED (observed, `invoke test -m collection_connector_bejerman --mode=update`):
    `odoo.tests.result: 3 failed, 16 error(s) of 30 tests` - e.g.
    `TestBejermanDebtMapping.test_open_row_maps_to_snapshot_entry` (module has no
    attribute `map_debt_row`), `test_queries_decode_json_in_json` (FAIL),
    `test_obtener_clientes_sends_empty_list_params` (FAIL),
    `TestBejermanConnector.test_get_customer_debt_kind_outstanding` (no
    `_bejerman_today`).
  - GREEN (observed): `odoo.tests.result: 0 failed, 0 error(s) of 30 tests`.
  - Baseline before any change: `0 failed, 0 error(s) of 15 tests`.
  - `bejerman_quotation_kinds` now defaults to `PRE` for new records and a blank value
    falls back to `PRE` at read time (existing connectors created before this change
    have it NULL, which would otherwise turn every `PRE` quotation into an invoice).

- 2026-10-03 T3 done. New models `collection.connector.bejerman.debt` (unique
  `(connector_id, external_invoice_id)`, index `(connector_id, customer_code)`, related
  stored `company_id`, `ondelete=cascade`, no stored `state`) and
  `collection.connector.bejerman.customer` (active customers only: code, name, canonical
  CUIT, seller code; unique `(connector_id, customer_code)`). A customer cache model was
  chosen over JSON blobs; it stores no `active` column because only enabled customers
  are cached (a disabled customer reads as unknown, exactly as before). Connector fields
  `bejerman_snapshot_refreshed_at` / `_customer_count` / `_debt_count` (readonly, not
  sensitive, no `groups` so internal users can read the "snapshot exists" marker).
  `_bejerman_refresh_snapshot()` reads clients + debt in one Registro -> Cierre session,
  maps (raw rows are freed before any DB work), then swaps inside one savepoint;
  duplicate composite ids keep the first row; any failure logs only the exception class
  and raises a generic `UserError`, previous snapshot intact.

  - Access rights: `base.group_user` read-only (1,0,0,0) and `base.group_system` full
    (1,1,1,1) on both models, plus a global `[('company_id', 'in', company_ids)]`
    `ir.rule` each. Reason: MCP `customer_debt` / `list_collection_customers` and the
    Add Debt picker call the connector as the calling internal user (no `sudo()` in
    `collection`), so the read path needs read ACL for `group_user`; only the refresh
    (admin button, or the cron as superuser) writes. Side benefit: the read path no
    longer touches the `group_system` credential fields, which an internal user could
    not read.
  - RED (observed): `0 failed, 11 error(s) of 41 tests` (e.g.
    `TestBejermanSnapshot.test_refresh_replaces_snapshot_in_one_session` ->
    `AttributeError ... no attribute '_bejerman_refresh_snapshot'`,
    `test_unique_external_invoice_id_per_connector` ->
    `KeyError: 'collection.connector.bejerman.debt'`).
  - GREEN (observed): `0 failed, 0 error(s) of 41 tests`. One intermediate run showed 2
    errors caused by my own test (a `MagicMock` patched onto a model class is picked up
    by the ORM's `_ondelete` scan); tests now patch with plain functions.
  - The existing `test_admin_only_credentials_and_button` asserted
    `data == ["views/..."]` and "no ir.model.access.csv"; that contradicted the new
    design, so it now pins the new data list.

- 2026-10-03 T4 done. `data/ir_cron.xml` (`noupdate`, 4 hours, code
  `model._bejerman_cron_refresh_snapshot()`); the cron method refreshes every active
  `type == bejerman` connector, each in its own savepoint, logging only the failure
  class. Button `action_bejerman_refresh_snapshot` (view `groups="base.group_system"`,
  hidden unless `type == 'bejerman'`; the method also refuses non-system users with
  `AccessError` and non-bejerman types with the generic "operation is not available"
  error, because a view `groups` attribute is not a server-side guard). Admin form shows
  last refresh and both counters (readonly). Manifest `data` lists security, view, cron.

  - RED (observed): `1 failed, 5 error(s) of 47 tests` (missing
    `action_bejerman_refresh_snapshot`, `_bejerman_cron_refresh_snapshot`, and the
    external id `ir_cron_bejerman_refresh_snapshot`).
  - GREEN (observed): `0 failed, 0 error(s) of 47 tests`.

- 2026-10-03 T5 done. `_bejerman_list_customers` and `_bejerman_get_customer_debt` read
  the snapshot models as the calling user (no SOAP, no credential access); `state` is
  computed per read from `_bejerman_today()` (company partner tz, else user tz, else
  UTC). Empty snapshot choice: before the first refresh
  (`bejerman_snapshot_refreshed_at` unset) both reads fail closed with the existing
  generic "not configured" `UserError` and make no SOAP call, instead of triggering a
  ~200 MB inline download; an empty-but-refreshed snapshot is valid and answers empty
  debt. `_bejerman_test_connection` no longer downloads the debt view (Registro,
  `ObtenerClientes`, seller view, Cierre; the refresh exercises the debt view). Optional
  live path: char field `bejerman_debt_filter_field` (admin-only); when set,
  `get_customer_debt` calls the configured debt view live with
  `[{"Campo": field, "Valor": <ERP customer code, zeros kept>}]` and needs no snapshot.
  That path runs on a `sudo()` record because the caller of
  `collection.connector.get_customer_debt` is the MCP/picker user (internal, not admin)
  and the credentials are `group_system`; only business rows are returned. Dead
  synthetic helpers (`map_customers`, `match_customer`, `map_customer_debt`,
  `map_invoices`, `is_outstanding`) were removed; `find_customer_row`,
  `customer_from_row`, `erp_customer_code`, `debt_filter` were added.
  - RED (observed): `4 failed, 12 error(s) of 57 tests` (snapshot reads did not exist
    yet: e.g. `TestBejermanSnapshotReads.test_no_snapshot_fails_closed_...` FAIL,
    `test_live_path_filters_the_debt_view_by_customer` ->
    `Invalid field 'bejerman_debt_filter_field'`, `test_connection_probe_then_cierre`
    FAIL on 5 vs 4 POSTs).
  - GREEN (observed): `0 failed, 0 error(s) of 57 tests`.
- 2026-10-03 T6 done. Manifest `19.0.1.0.0` -> `19.0.1.1.0` (RED:
  `AssertionError: '19.0.1.0.0' != '19.0.1.1.0'`, `1 failed of 58`). No migration
  script: `-u` creates the new tables/ACL/rules through the ORM, the cron record is new
  (so its `noupdate="1"` does not skip it), and a NULL `bejerman_quotation_kinds` on
  pre-existing connectors is resolved to `PRE` at read time. `readme/DESCRIPTION.md` and
  `openspec/specs/bejerman-collection-connector/spec.md` updated (RFC 2119 +
  Given/When/Then: real payload handling, debt row mapping, refresh, entry points,
  snapshot reads, live filtered debt).

  - Real-ERP check of the shipped mapping (counts only): 171,076 rows decoded as a list,
    6,416 active customers cached, 1,254 open debts (746 invoice, 508 quotation), 0
    blank due dates, `map_open_debt` 0.19 s, whole fetch+map 24.5 s, peak RSS 758 MB.

- 2026-10-03 T7 done (decision: disabled customers are not brought). The refresh passes
  `customer_codes` (the enabled customers being cached) to `mapping.map_open_debt`, so
  debt of disabled customers and of codes absent from `ObtenerClientes` is never stored;
  the debt count drops accordingly. The optional live path already resolves the customer
  through `find_customer_row` (enabled only), so a disabled customer returns the empty
  shape and the debt view is never requested; pinned by a test.
  - RED (observed): `1 failed, 1 error(s) of 61 tests` -
    `test_debt_of_disabled_or_unknown_customers_is_not_stored`
    (`'FHK|00004|A|00007777' unexpectedly found`) and
    `test_map_open_debt_restricts_to_given_customer_codes`
    (`unexpected keyword argument 'customer_codes'`). The live-path test passed at once,
    confirming the path was already safe.
  - GREEN (observed): `0 failed, 0 error(s) of 61 tests`.
  - Real-ERP recount with the shipped mapping (counts only, one quick re-download): open
    debts 1,254 -> **1,126** (667 invoices, 459 quotations), customers with debt 568 ->
    **497**; 128 rows of 71 disabled customers are excluded. Cached customers stay
    6,416.

## Verification

- `invoke test -m collection_connector_bejerman --mode=update` (Seedian root, `devel`
  DB): `odoo.tests.result: 0 failed, 0 error(s) of 58 tests` (final run after lint
  reformat; baseline before the change was 15 tests).
- `pre-commit run --files <30 addon files, archive excluded>`: exit 0, every hook Passed
  (ruff fixed/reformatted line lengths on the first pass; second run clean). The
  optional-checks pylint prints the pre-existing `C8101 manifest-required-author`
  ('Eynes') on `__manifest__.py` (author is `Seedian`); it is non-blocking and was not
  touched.

## Open decisions for the user

- Types other than `PRE` are invoices by decision (2 open `PRS`, and `ND`/`DHK`/
  `DHS`/`FMK`/`FEM`/`FEH`/`FIH`); say so if `PRS`/`PRM` should be quotations (set
  Bejerman Quotation Kinds `PRE,PRS`).
- 8 open rows are in currency `2`; amounts used are the local-currency columns.
- Native review of the root commit remains pending (see Delivery).

## Next step

Configure the connector (debt scenario `TEST`, view `Saldos al día/*`) and run Refresh
Debt once. When the filtered child view exists, set Bejerman Debt Filter Field (for
example `CVE_CODCLI`) on the connector.
