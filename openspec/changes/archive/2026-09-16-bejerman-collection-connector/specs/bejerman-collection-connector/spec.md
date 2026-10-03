# Bejerman Collection Connector Specification

## Purpose

Read-only Bejerman adapter for `collection.connector`. Sqlite-compatible raw reads; fail
closed; no receipt writes.

## Requirements

### Requirement: Type registration

MUST inherit `collection.connector`, `selection_add` `bejerman`, cascade on uninstall.

#### Scenario: Type is selectable

- GIVEN installed addon
- WHEN creating a connector then uninstalling
- THEN `bejerman` MUST be valid until uninstall cascades it

### Requirement: Raw read operations

MUST implement `test_connection`, `list_sellers`, `list_customers`, and
`get_customer_debt` as sqlite raw shapes for `_format_*`. MUST NOT format MCP payloads.

#### Scenario: Four ops return raw rows

- GIVEN working bejerman connector
- WHEN the four read ops run
- THEN sqlite raw keys MUST match without MCP `source`

### Requirement: Receipt write unavailable

MUST NOT implement `create_receipt`; dispatch MUST raise generic unavailable `UserError`
with no write.

#### Scenario: create_receipt fails closed

- GIVEN a bejerman connector
- WHEN `create_receipt` is dispatched
- THEN MUST raise that `UserError` with no Bejerman write

### Requirement: Test Connection

MUST close the session after the probe. Success requires Registro, ObtenerClientes, and
both Query views. Refusal MUST raise a generic admin `UserError`.

#### Scenario: Full probe then close

- GIVEN working TABLAS and both Query views
- WHEN Test Connection runs
- THEN it MUST succeed and close the session

### Requirement: Seller mapping

Query keys MUST map by alias suffix; padded codes trimmed; inactive omitted.
`commission_percent` MUST be 0–100; zero listable.

#### Scenario: Seller suffix map

- GIVEN prefixed keys, padded codes, inactive seller, and zero commission
- WHEN `list_sellers` runs
- THEN ids MUST be suffix-mapped and trimmed; inactive omitted; zero remains

### Requirement: Seller-scoped customers

`list_customers` MUST be seller-scoped with AFIP CUIT `XX-XXXXXXXX-X` on rows and
lookup; omit other-seller and inactive.

#### Scenario: Seller-scoped canonical customers

- GIVEN mixed customers for E and others, plus 11-digit CUITs
- WHEN `list_customers` runs for E
- THEN only E's active customers MUST appear with canonical CUIT

### Requirement: Debt mapping

FC-style MUST map to `invoice`; configured order/budget to `quotation`; else `invoice`.
Only `open`/`overdue` with `balance` > 0. Unknown, inactive, or other-seller MUST return
`{customer: None, invoices: []}`.

#### Scenario: Kind and outstanding

- GIVEN mixed FC, order/budget, paid, and zero-balance rows
- WHEN `get_customer_debt` runs
- THEN outstanding FC MUST be `invoice`, order/budget `quotation`; paid/zero omitted

#### Scenario: Unknown customer

- GIVEN unknown identification
- WHEN `get_customer_debt` runs
- THEN MUST return `{customer: None, invoices: []}`

### Requirement: Prefix-free identifiers

Query-generated prefixes MUST NOT appear in emitted ids or codes.

#### Scenario: Prefixes stripped

- GIVEN Query keys with generated prefixes
- WHEN sellers, customers, or debt rows are emitted
- THEN emitted ids MUST omit generated prefixes

### Requirement: No leakage

Credentials, URLs, SOAP, SQL/view internals, and Bejerman ErrorMsg MUST NOT appear in
`UserError` or MCP-visible messages.

#### Scenario: Errors hide internals

- GIVEN SOAP, view, or credential failure
- WHEN any bejerman op raises
- THEN UserError and MCP-visible text MUST omit those internals

### Requirement: Admin-only credentials

Credentials and Test Connection MUST be `base.group_system` with masked password. MUST
inherit collection connector form. MUST NOT add menus, MCP, hooks, sample data, or
Bejerman writes.

#### Scenario: Admin-only masked credentials

- GIVEN a non-system user and a system administrator
- WHEN they open a bejerman connector
- THEN only the administrator MUST see masked credentials and Test Connection

### Requirement: Company isolation

Reads MUST use the connector of `env.company`. A MUST NOT receive B's Bejerman data.

#### Scenario: Isolation

- GIVEN B's bejerman connector is not selected by A
- WHEN A lists or reads debt
- THEN the result MUST NOT come from B's connector

### Requirement: Missing ERP grants

Missing ObtenerClientes or either Query view MUST fail closed with a generic
`UserError`.

#### Scenario: Missing grants fail closed

- GIVEN refused ObtenerClientes or a missing Query view
- WHEN Test Connection or a read op runs
- THEN MUST raise a generic `UserError` with no leak
