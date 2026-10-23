# Seller commission on the untaxed amount (Bejerman IA CRIS)

Objective: pay the seller commission on the untaxed share (`NETO + NGEX`) of what was
collected, read from the Bejerman sales VAT book view and crossed with `Saldos al día`.
Branch `feat/untaxed-commission` in `collection_connector_bejerman` and `collection`.
Delivery `ask-on-risk`; runner `invoke test -m <addon> --mode=update` (seedian root).

## Specs

- S1 Cross both queries: "In Saldos al Dia we have the amount each customer has open. But
  to calculate the commission of the seller we have to take the Neto amount of the debt
  (For invoices, because in Presupuestos Neto = Total). So we should cross both queries to
  get that value." The second query is `Libro IVA Ventas/IA CRIS` (scenario `TEST` on the
  customer's connector), configurable on the connector next to the debt query. Match key:
  `COMP_CODINT` + point of sale + letter + number (parsed from `COMPROBANTE`, e.g.
  `A 00004-00056383`) + `CLIENTE_COD`, against the debt row's `CVETCO_COD`, `CVE_CODPVT`,
  `CVE_LETRA`, `CVE_NRO`, `CVE_CODCLI`.
- S2 Neto definition (user answer "B"): `NETO + NGEX`, i.e. everything except taxes and
  perceptions.
- S3 Partial open amount: "In case certain debt has a partial open amount, we should
  calculate a Neto related to that." The snapshot stores `amount_untaxed` and
  `balance_untaxed = amount_untaxed × balance / amount`.
- S4 Presupuestos (quotation kinds): untaxed = total, no lookup.
- S5 Invoice with no IA CRIS match (user answer "A"): base stays the total, and the refresh
  logs which vouchers did not match.
- S6 Commission rule (user: "yes, that's the rule. The comission must consider the
  proporcionally neto and also that the seller has collected for that voucher"):
  `commission = applied × amount_untaxed / amount × %`, rounded per row as today.
- S7 Connectors with no untaxed amount (SQLite, Bejerman without the view configured, lines
  stored before this change) keep today's commission exactly (`applied × %`).
- S8 A failed IA CRIS read fails the refresh and keeps the previous snapshot, like the debt
  view.

Assumptions: the customer widens IA CRIS to cover every open voucher (user: "yes, they will
widen the view to cover all open vouchers"). The live per-customer path
(`bejerman_debt_filter_field`, unset in `devel`) sends no untaxed amount and keeps today's
commission. `customer_debt` (MCP) does not expose the new field.

## Tasks

- [x] T1 S1-S5, S8 — `collection_connector_bejerman`: untaxed view settings, IA CRIS
  mapping, snapshot `amount_untaxed`/`balance_untaxed`, payload `amount_untaxed` — inline
  (no writer trigger: one unit, read inline) — commit `6c4fb6c`
- [x] T2 S6-S7 — `collection`: line `invoice_amount_untaxed` from the connector, commission
  on the untaxed share — inline — commit `b54f452` (collection repo)
- [x] T3 Real refresh on local `devel`, hand-check commissions — inline

## Log

- L1 (2026-10-23, user): "ok. I have seen the file. The thing is the following. In Saldos al
  Dia we have the amount each customer has open. But to calculate the commission of the
  seller we have to take the Neto amount of the debt (For invoices, because in Presupuestos
  Neto = Total). So we should cross both queries to get that value. In case certain debt
  has a partial open amount, we should calculate a Neto related to that. Make me a plan to
  do so and i will tell you"
- L2 Evidence 2026-10-23: IA CRIS read live via the `devel` connector (830 rows, Sep 2026).
  Join on `COMP_CODINT` matched 188 of 338 September open-debt rows, all `TOTAL` equal to
  the debt amount; unmatched were `PRE` and `DHK`. `TOTAL = NETO + IVA + NGEX + perceptions`
  on every row; no duplicate vouchers.
- L3 Decisions: widen view (yes), Neto = `NETO + NGEX` (B), unmatched invoice = total (A),
  commission = applied × untaxed/amount × % (confirmed). Plan approved: "yes, go ahead".
- L4 Naming: `amount_untaxed` (Odoo convention) instead of "net", because `summary.net_total`
  already means "net of credit notes".
- L5 T1 evidence: RED 12 errors of 11 new tests (missing functions/fields); GREEN 11/11.
  Full module on `devel`: 164/166; the 2 failures
  (`TestBejermanRefreshEntryPoints.test_cron_refreshes_active_bejerman_connectors_in_isolation`,
  `test_cron_survives_a_failure_notice_it_cannot_post`) also fail on the base commit
  (stash run): `devel` holds a real active connector named "Bejerman". Review assess on
  `6c4fb6c`: medium, `under_budget` (pending in the slice).
- L6 `devel` has `collection.mcp_trusted_seller_header` set, so in-process MCP tests of
  `collection` fail there at baseline; full suites run on a fresh `untaxed_check` DB.

- L7 T2 evidence: RED (KeyError `invoice_amount_untaxed` / `amount_untaxed`); fresh DB
  `untaxed_check`: both suites 1486 tests, then `collection` 1320/1320 after updating the
  two connector key-set tests for the new `amount_untaxed` key; the MCP `customer_debt`
  exact-key test passes unchanged (field popped). The 2 Bejerman cron failures do not
  occur on the fresh DB.
- L8 T3 evidence (`devel`, connector 4520 set to `TEST` + `Libro IVA Ventas/IA CRIS`):
  1087 open rows, 637 invoices, 186 with untaxed < total (36 partial); 449 invoices
  unmatched (IA CRIS still covers Sep 2026 only; logged with sample ids). Hand check
  `FHK|00004|B|00028984`: 832,048.72 → untaxed 687,643.57 (÷1.21); balance 81,799.15 →
  67,602.60; commission at 5% on that balance = 3,380.13.
- L9 Native review `collection` b54f452 (risk + reliability, consent granted): approved,
  acknowledged. Advisory: credit-note lines would keep the gross base (not reachable: lines
  are outstanding invoices, `amount_applied >= 0`, Bejerman drops balance <= 0); an explicit
  0 `amount_untaxed` becomes the total (intended, commented). No change.
- L10 Native review `collection_connector_bejerman` 6c4fb6c (risk + reliability, consent
  granted): approved, acknowledged. Advisory follow-ups, not done: a view with the wrong
  columns or an empty answer drops every row and only shows as "N unmatched"; no test for
  the legacy `amount_untaxed` 0 → total fallback nor for a blank NGEX.
- L11 Close: branch `feat/untaxed-commission` in both repos, not pushed. Engram mirror
  pending (no memory tool in this session).
