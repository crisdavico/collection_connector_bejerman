# Debt-free customers for advance payments

Objective: let a seller find, and load an advance for, a customer of theirs with no open debt.
Branch: `feat/debt-free-customers` in `collection_connector_bejerman` and `collection_connector_bejerman_kras`.
Delivery: ask-on-risk. Tests: `invoke test -m collection_connector_bejerman_kras` from the seedian root.

## Specs

- **S1** (user report, verbatim): "sometimes the sellers wants to load collections for customers
  that have no debt. like an advance payment. the thing is when they want to load that, the agent
  does not find the customer they mention (and the customer exists)."
- **S2** (user decision, verbatim): "go with the customer record seller_code option". A seller's
  customers are those with an open document (invoice, quotation or credit note) of theirs **plus**
  the customers whose Bejerman customer master names them (`collection.connector.bejerman.customer.seller_code`),
  in the snapshot listing and in the snapshot and live (kras) debt reads.
- **S3**: debt stays scoped by document seller: a customer listed only through its master shows no
  documents and no credit of another seller (empty debt, `pending_total` 0, payment goes on account).
- **S4** (consequence, assumption): when a seller's query matches more than one of their customers
  (one by documents, one by master), the lookup is ambiguous and reads as unknown; it never picks one.
- **S5**: docs, readmes, docstrings and field comments that state the old rule are updated; the agent's
  `docs/functional-workflow.md` decision log records the change.

## Tasks

| ID | Specs | Route | Status | Commit |
|----|-------|-------|--------|--------|
| T1 | S2-S4 | inline | done (RED 6 tests, GREEN 151/153 + 40/40; 2 known env cron failures) | bejerman 90a308d, kras 33d377c |
| T2 | S5 (Odoo docs) | inline | done | bejerman 90a308d, kras 33d377c |
| T3 | S5 (agent decision log) | inline | open | |

## Log

- **L1** (2026-11-13, user): "i have a problem that my customer reported. the thing is that sonetimes
  the sellers wants to load collections for customers that have no debt. like an advance payment. the
  thing is when they want to load that, the agent does not find the customer they mention (and the
  customer exists). try to understand why this happen and propose me a solution"
- **L2** (2026-11-13): cause: `_bejerman_seller_customers` builds the list only from open debt rows with
  the seller's code (2026-10-29 decision). Odoo's write path (`receipts` with empty `applications`) and the
  agent's `propose` already handle an all-on-account advance; the advance is a Factura advance
  (`collection_sheet_report.py:566`).
- **L3** (2026-11-13, user): "go with the customer record seller_code option"
- **L4**: Risk item 2 (seller data visibility scope). Engram mirror pending: no Engram tools in this session.
- **L5** (2026-11-13): RED observed (6 seller-scope tests). GREEN: kras 151/153 and base 40/40; the 2
  failures are `TestBejermanRefreshEntryPoints` cron tests that fail on the base too (devel DB has an extra
  active "Bejerman" connector). S4: `0160` shared by E's document customer and E's master customer is now
  ambiguous (was resolved to the document customer); the full code still resolves.
