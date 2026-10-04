# Bejerman sellers from the debt view

## Objective

Build the Bejerman connector's seller list from the debt view that the snapshot refresh
already downloads, so no extra Bejerman request is needed, and keep commission, phone and
enabled maintained in Odoo.

## Problem

Bejerman has no seller view or seller table (verified live 2026-10-03: `Vendedores/*`,
`Vendedor/*`, `Zonas/*`, `ObtenerVendedores`, `ObtenerVistas` all answer `ERR`; the SDK docs
list no seller operation). `_bejerman_list_sellers` queries `bejerman_seller_scenario` /
`bejerman_seller_view` and `map_sellers` needs `Codigo/Descripcion/Habilitado/Comision/
Telefono`, so the seller import and Test Connection can never succeed.

## Why

The debt view `Saldos al día/*` carries the voucher seller on every row (verified live
2026-10-04): `CVEVEN_COD` (code) and `VEN_DESC` (name), one name per code. 171,076 rows,
47 distinct sellers on all rows, 25 on open rows. The refresh already downloads it every
4 hours, so sellers come at zero extra requests (user decision: reduce Bejerman requests).

## Scope (authorized)

- Addon `collection_connector_bejerman` only (own git repo). Do **not** modify the
  `collection` addon: its repo has unrelated uncommitted work on `feat/voucher-validations`.
- Seller source: all rows of the debt view (not only open rows), user decision 2026-10-04.
- Odoo keeps commission (binding `commission_percent`), phone (bound user's partner phone)
  and enabled (`company.enabled_seller_ids`). `_bejerman_list_sellers` merges them back so
  the generic import never overwrites admin values.
- New sellers: `active=False`, `commission_percent=0`, blank mobile.
- Bejerman name wins on every import. A seller absent from Bejerman keeps its binding and
  is just no longer listed. Customer scoping stays on the customer's assigned seller
  (`Cliente_VendedorCodigo`), unchanged.
- Commission editable on the connector's seller bindings, Bejerman connectors only, via a
  view inherited inside this addon.
- Test Connection: no seller-view stage anymore.

## Constraints

- One debt-view download per refresh; the seller list must not trigger a Bejerman call.
- Seller list reads the snapshot; no snapshot yet means the existing "refresh first" error.
- No secrets or raw payloads in messages or logs (existing module policy).
- `bejerman_seller_scenario` / `bejerman_seller_view` stay as fields (the `collection`
  settings wizard references them) but are no longer used or shown in the Bejerman form.
  Follow-up outside scope: drop them from the `collection` wizard.

## Known facts (live, 2026-10-04)

- 37 of 1,254 open vouchers have a voucher seller different from the customer's assigned
  seller (32 customers); 7 customers have open debt from 2+ sellers. Scoping unchanged.
- Generic import replaces `enabled_seller_ids` (existing behavior): the manually enabled
  `kras.collections` user (no binding) will be dropped from kras on the first import.
  User informed.

## TDD

- Mode: strict TDD **on** (source: user global config "Strict TDD Mode: enabled").
- Runner: `invoke test -m collection_connector_bejerman`, or inside the running container
  `docker exec seedian-odoo-1 odoo -d <tmp db> -i collection_connector_bejerman
  --test-enable --test-tags /collection_connector_bejerman --stop-after-init
  --http-port=18169 --gevent-port=18172` (then `dropdb`).
- Known base failures: 8 errors `column "autopost_bills" of relation "res_partner" does
  not exist` in raw-SQL helpers (pre-existing, not caused here).

## Delivery

- Branch `feat/bejerman-sellers-from-debt-view` in the addon repo; one Conventional Commit
  per task. Strategy `ask-on-risk`; forecast ~350 authored lines. RDD: off (clone-local).

## Tasks

- [x] T0 Commit the already-verified stage-specific Test Connection errors (route: inline).
      Commit `8f48a60`. Evidence: module suite 0 failures / 8 known errors of 71 tests
      (2026-10-04 spot check); live devel Test Connection shows the stage message.
- [x] T1 Seller snapshot: `map_debt_sellers(rows)` over all debt rows, new seller snapshot
      model, refresh stores sellers in the same swap (route: delegated writer).
      Commit: `feat(collection_connector_bejerman): snapshot sellers from the debt view`
      Commit `ffc6645`. Manifest bumped to 19.0.1.2.0 (new model).
      RED (2026-10-04): `1 failed, 19 error(s) of 79 tests` = 8 known `autopost_bills` errors
      plus the 4 new mapping tests, the new seller snapshot tests and the version test.
      GREEN: `0 failed, 8 error(s) of 79 tests` (the 8 known errors only). Extra check: in the
      throwaway DB the missing `res_partner.autopost_bills` and `res_company` columns were
      added by hand so the raw-SQL tests run: `0 failed, 0 error(s) of 79 tests`, which
      also exercises the new company-scoping and ACL assertions. One download unchanged:
      the 4 SOAP calls per refresh are asserted.
- [x] T2 `_bejerman_list_sellers` from the seller snapshot merged with Odoo values; Test
      Connection without seller view; hide seller scenario/view in the form (route:
      delegated writer).
      Commit: `feat(collection_connector_bejerman): list sellers from the snapshot`
      Commit `29e2178`. `map_sellers` and its `_commission` helper
      removed; Test Connection is Registro, ObtenerClientes, Cierre (3 calls).
      RED: `2 failed, 17 error(s) of 81 tests` (8 known errors plus the new seller list,
      import and Test Connection tests, and the 3 updated ones).
      GREEN: `0 failed, 8 error(s) of 81 tests` (the 8 known errors only); with the
      `res_partner` / `res_company` columns added by hand in the throwaway DB so the
      raw-SQL tests run: `0 failed, 0 error(s) of 81 tests`.
      ACTUAL IMPORT BEHAVIOUR (asserted by tests, decision needed): `list_sellers()` of
      `collection` (`_format_seller_list`) drops `active=False` rows, so an unbound seller
      is neither bound nor given a user by the import, and an import with no enabled
      bound seller replaces `enabled_seller_ids` with an empty set. New sellers therefore
      cannot be onboarded through the import alone; see the final report.
- [x] T3 Editable commission on Bejerman seller bindings (inherited view) (route:
      delegated writer).
      Commit: `feat(collection_connector_bejerman): edit seller commission on Bejerman bindings`
      Commit `ec10bb0`. The inherited form view sets the binding
      list `commission_percent` to `readonly="parent.type != 'bejerman'"`. No ACL change in
      `collection` was needed: `group_collection_manager` and `base.group_system` already
      hold write on `collection.connector.seller.binding` (and on the connector).
      RED: `2 failed, 8 error(s) of 86 tests` (the 8 known errors; the 2 failures were
      Form-based drafts, replaced by an arch assertion because `odoo.tests.Form` does not
      apply the list-level readonly). The arch test fails against the old `readonly="1"`.
      GREEN: `0 failed, 8 error(s) of 84 tests` (the 8 known errors only); with the
      throwaway-DB column shim: `0 failed, 0 error(s) of 84 tests`. The ORM tests (admin
      and manager write the commission; next import keeps it) pass without a view change,
      which is the evidence that no ACL work is needed.
- [ ] T4 Live check on `devel`: upgrade, refresh, list sellers (route: inline).

## Acceptance criteria

- Refresh makes exactly the same Bejerman calls as before and stores 47 sellers on devel.
- `list_sellers` returns code/name from the snapshot with Odoo commission/phone/enabled;
  new sellers inactive with commission 0.
- Re-import after the admin edits commission/phone/enabled keeps those values.
- Test Connection passes on devel with the seller fields empty.
- Module suite: 0 failures (8 known base errors allowed).

## Progress

- 2026-10-04: exploration done; design approved by user; document created.

## Next step

T0.
