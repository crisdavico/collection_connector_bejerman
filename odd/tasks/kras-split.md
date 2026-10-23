# Split the Kras debt pipeline into collection_connector_bejerman_kras

Objective: keep `collection_connector_bejerman` generic and move everything particular to
the customer Kras into a new addon `collection_connector_bejerman_kras`, enabled per
connector. Branch `feat/kras-split` (base); new repo `collection_connector_bejerman_kras`.
Delivery `ask-on-risk`; runner `docker compose run --rm odoo odoo --test-enable` on a
scratch DB (seedian root).

## Specs

- S1 Scope: "In collection_connector_bejerman we have things that are really particularly
  of my customer kras. Maybe it is a good idea to separate that in another module". Kras
  parts (user answer): "Untaxed commission, Debt view layout, Sellers from debt view,
  Quotations (PRE)". The live per-customer path reads the same debt view, so it moves too.
- S2 Name: "use the name to match siblings" → `collection_connector_bejerman_kras`.
- S3 Per-connector switch: "yes, other clients share the same database". The base adds
  `bejerman_profile` (`standard`); the Kras addon adds `kras` and acts only on `kras`
  connectors. A `standard` connector never reads the Kras views or stores untaxed amounts.
- S4 Migration: "yes, all current Bejerman connectors are Kras". Installing the Kras addon
  marks every existing Bejerman connector `kras`; data of the moved fields is kept.
- S5 Base keeps: SOAP session, settings, Test Connection, customers (`ObtenerClientes`),
  snapshot storage and refresh orchestration, cron, sync status and notices, freshness,
  "Entered in the ERP", seller bindings and the enable wizard, `credit_total`. A
  `standard` connector has no debt source: its refresh fails closed with a configuration
  error and keeps the previous snapshot (assumption: never serve an empty debt as real).
- S6 Kras behaviour is unchanged: same snapshot, same untaxed amounts, same logs.

## Tasks

- [x] T1 S3 S5 base: profile, snapshot-source hooks, Kras code removed, seam tests,
      pre-migration handing the moved fields to the Kras addon (inline; chain on
      `feat/kras-split-chain`, see L9)
- [x] T2 S1 S2 S3 S4 S6 Kras addon: fields, mapping, overrides, views, install hook,
      moved tests, README, es_AR (inline; Kras repo chain on
      `feat/kras-split-chain`, see L10)
- [x] T3 S4 S6 upgrade on a copy of the devel DB: counts and untaxed amounts kept,
      profiles set (inline; evidence L6)

## Log

- L1 2026-10-23 user: "In collection_connector_bejerman we have things that are really
  particularly of my customer kras. Maybe it is a good idea to separate that in another
  module (collection_bejerman_kras). Make me a proposal to do that. Ask me anything you
  need"
- L2 Proposal accepted; answers quoted in S1-S4. "yes, go ahead with
  collection_bejerman_kras", then "use the name to match siblings".
- L3 Routing: inline. The two addons depend on each other (Kras overrides base hooks), so
  they are not independent units; no writer trigger. Engram mirror pending (no memory
  tools in this session).
- L4 Tests: the existing suite runs against a fake ERP serving the Kras debt view, so it
  moves with the Kras addon (end to end over the base machinery). The base keeps the
  transport and Test Connection tests, the shared fake ERP in `tests/common.py`, and new
  seam tests with a stubbed snapshot source.
- L5 2026-10-23 tests. Baseline (base before the split, scratch DB): 167 tests, 0 failed.
  After: base alone 35 tests, 0 failed; base + Kras 180 tests, 0 failed (13 new: base
  profile seam and mapping, Kras profile and install hook). Moved Kras tests changed only
  their imports, the logger of the untaxed log line (now the Kras addon's) and the view
  they read the Kras fields from.
- L6 2026-10-23 upgrade on copies of devel (connector 4520, 1081 debt rows). One command
  (`-u collection_connector_bejerman -i collection_connector_bejerman_kras`): settings,
  1081 rows, amount/balance untaxed sums (664384932.43 / 588652327.42), 6538 customers,
  46 sellers and credit sum identical; profile `kras`; fields owned by the Kras addon.
  Base alone without the pre-migration dropped every Kras column (settings lost), so the
  base got `migrations/19.0.2.0.0/pre-migration.py`, which hands the moved fields to the
  Kras addon first. With it: base alone keeps every column (profile `standard`, refresh
  fails closed); installing Kras afterwards gives the same figures as the one command.
  The upgrade also removed the long-unused `bejerman_seller_scenario/view` field records
  of devel's older install.
- L7 Delivery: two repos, one commit each; the base diff is mostly tests moved to the
  Kras addon. The Kras repo is local only (no remote yet); seedian's `addons.yaml` has a
  local, uncommitted entry for it and `repos.yaml` needs one once the remote exists.
- L8 2026-10-23 independent verifier: S1-S6 PASS, no blockers (base and base + Kras
  suites green; DB-copy upgrades byte-identical, debt md5 065e4ba4… in devel and both
  copies). Advisory taken as an S6 defect: the untaxed "left out" warnings were logged
  inside the session and before the skipped-rows warning. Fixed with the base hook
  `_bejerman_log_snapshot_read`, called after the session and after the skipped-rows log;
  pinned by `test_refresh_logs_skipped_rows_before_the_untaxed_left_out` (RED "1 not
  less than 0" with the old order, GREEN after). Suites: 181 tests, 0 failed.
  Other advisories left as is: the install hook marks every existing Bejerman connector
  kras (S4 as answered); the base suite alone no longer covers the snapshot machinery
  (L4).
- L9 2026-10-23 native review: the single base commit exceeded the reviewer context
  budget (`lens_context_budget_exceeded`, 6120 lines). User chose "Split and review".
  Base rebuilt as `feat/kras-split-chain` from `fffd512`, each slice green:
  fe32554 shared fake ERP (167 tests) and eee3f3c profile + extension points with the
  Kras defaults (170): reviewed together, approved. 9894988 and e9a95a0 move end-to-end
  tests out (66): reviewed, approved. b2a6335 and f345753 keep generic mapping tests and
  move the connector tests and fixtures (32): reviewed, approved. 87b5dd7 the code move
  and pre-migration (35 tests; high risk, item 1): reviewed alone, approved; its cheap
  advisories fixed in 003f3ac. Every approval was acknowledged. Advisories left: base-only
  coverage moved to the Kras suite (L4); no automated test of the pre-migration (proven
  on DB copies, L6); a base-only upgrade serves the old snapshot without untaxed amounts
  until refreshed (install both in one run). `feat/kras-split` is the single-commit
  reference with the same final tree.
- L10 2026-10-23 Kras repo rebuilt as `feat/kras-split-chain`: fe7740d tooling root (no
  base to review against); 167a15a profile code, install hook and profile tests (41
  tests; high risk, item 1): reviewed alone, approved; 84b9e9e + 1ac4918 moved tests
  (90): reviewed, approved; 1dc216e remaining moved tests (181 with the base): reviewed,
  approved; d919ebf docs and es_AR: under budget, pending. Final tree identical to the
  single-commit reference 7ce3774. Every approval acknowledged. Advisories left as
  follow-ups (all behaviour or tests moved unchanged from fffd512): an unusable VAT book
  row drops the invoice instead of keeping its total, as the docstring claims; the live
  path sends no untaxed amount; quotations with a blank issue date are dropped; a few
  moved tests assert weakly. Upgrade re-run with the final chains (guard change in
  003f3ac): one command and base-then-Kras both keep settings, 1081 rows and the
  untaxed sums; profile `kras`.
