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

- [ ] T1 S1-S5, S8 — `collection_connector_bejerman`: net view settings, IA CRIS mapping,
  snapshot `amount_untaxed`/`balance_untaxed`, payload `amount_untaxed` — inline — commit:
- [ ] T2 S6-S7 — `collection`: line `invoice_amount_untaxed` from the connector, commission
  on the untaxed share — inline — commit:
- [ ] T3 Real refresh on local `devel`, hand-check commissions — inline

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
