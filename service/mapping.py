# Copyright 2026 Seedian
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

"""Suffix-map Bejerman Query/TABLAS rows into sqlite raw shapes."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import date
from typing import Any

_INACTIVE = frozenset({0, "0", "false", "False", "n", "N", "no", "No"})


def value_by_suffix(row: Mapping[str, Any], *suffixes: str) -> Any:
    """Return the first cell whose key equals or ends with a suffix."""
    for suffix in suffixes:
        for key, val in row.items():
            if key == suffix or str(key).endswith(suffix):
                return val
    return None


def trim_code(value: Any) -> str:
    """Strip whitespace and leading-zero pad; keep a lone ``0``."""
    if value is None:
        return ""
    text = str(value).strip()
    if not text:
        return text
    stripped = text.lstrip("0")
    return stripped if stripped else "0"


def canonicalize_cuit(value: Any) -> str:
    """Format 11-digit values as AFIP ``XX-XXXXXXXX-X``; otherwise strip."""
    if value is None:
        return ""
    text = str(value).strip()
    digits = "".join(char for char in text if char.isdigit())
    if len(digits) == 11:
        return f"{digits[:2]}-{digits[2:10]}-{digits[10]}"
    return text


def quotation_kind_set(raw: Any) -> set[str]:
    """Parse comma-separated (or sequence) quotation document-kind codes."""
    if raw in (None, False, ""):
        return set()
    if isinstance(raw, (set, list, tuple)):
        parts: Iterable[Any] = raw
    else:
        parts = str(raw).split(",")
    return {str(part).strip().upper() for part in parts if str(part).strip()}


def document_kind(raw: Any, quotation_kinds: Any = None) -> str:
    """Map FC-style → invoice; configured order/budget → quotation; else invoice."""
    text = str(raw or "").strip().upper()
    if text.startswith("FC"):
        return "invoice"
    if text in quotation_kind_set(quotation_kinds):
        return "quotation"
    return "invoice"


def row_is_active(value: Any) -> bool:
    """Treat missing active as True; 0/false/N as inactive."""
    if value is None:
        return True
    if isinstance(value, str) and not value.strip():
        return True
    return value not in _INACTIVE


def as_rows(payload: Any) -> list[Mapping[str, Any]]:
    """Coerce a Query/TABLAS JSON payload to a list of mappings."""
    if payload is None:
        return []
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, Mapping)]
    raise TypeError("Bejerman payload is not a list")


def _text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _date(value: Any) -> str:
    text = _text(value)
    if "T" in text:
        return text.split("T", 1)[0]
    return text


def _money(value: Any) -> float:
    try:
        return round(float(value or 0), 2)
    except (TypeError, ValueError):
        return 0.0


def _commission(value: Any) -> float | None:
    try:
        percent = float(value if value is not None else 0)
    except (TypeError, ValueError):
        return None
    if percent < 0 or percent > 100:
        return None
    return percent


def map_sellers(payload: Any) -> list[dict[str, Any]]:
    """Sqlite-raw seller rows; inactive omitted; commission 0–100 inclusive."""
    sellers = []
    for row in as_rows(payload):
        if not row_is_active(value_by_suffix(row, "active", "Habilitado")):
            continue
        commission = _commission(value_by_suffix(row, "commission_percent", "Comision"))
        if commission is None:
            continue
        seller_id = trim_code(value_by_suffix(row, "id", "Codigo"))
        if not seller_id:
            continue
        sellers.append(
            {
                "id": seller_id,
                "name": _text(value_by_suffix(row, "name", "Descripcion")),
                "mobile": _text(value_by_suffix(row, "mobile", "Telefono")),
                "active": True,
                "commission_percent": commission,
            }
        )
    return sellers


def find_customer_row(
    payload: Any,
    external_seller_id: Any,
    identification: Any,
) -> Mapping[str, Any] | None:
    """Raw row of the unique active seller-scoped customer with that CUIT."""
    wanted_seller = trim_code(external_seller_id)
    wanted = canonicalize_cuit(identification)
    matches = []
    for row in as_rows(payload):
        mapped = _map_customer_row(row)
        if mapped is None or mapped["identification"] != wanted:
            continue
        seller_code = trim_code(value_by_suffix(row, "VendedorCodigo", "seller_id"))
        if seller_code == wanted_seller:
            matches.append(row)
    return matches[0] if len(matches) == 1 else None


def customer_from_row(row: Mapping[str, Any]) -> dict[str, Any] | None:
    """Sqlite-raw customer for a raw TABLAS row, or None when disabled."""
    return _map_customer_row(row)


def erp_customer_code(row: Mapping[str, Any]) -> str:
    """Customer code exactly as the ERP stores it (stripped, zeros kept)."""
    return _text(value_by_suffix(row, "Cliente_Codigo", "id", "customer_code"))


def debt_filter(field: str, erp_code: str) -> list[dict[str, str]]:
    """Query-view filter selecting one customer's rows."""
    return [{"Campo": field, "Valor": erp_code}]


def map_customer_rows(payload: Any) -> list[dict[str, Any]]:
    """Active customers for the snapshot cache, first row wins per trimmed code."""
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in as_rows(payload):
        mapped = _map_customer_row(row)
        if mapped is None or mapped["customer_code"] in seen:
            continue
        seen.add(mapped["customer_code"])
        rows.append(
            {
                "customer_code": mapped["customer_code"],
                "name": mapped["name"],
                "identification": mapped["identification"],
                "seller_code": trim_code(
                    value_by_suffix(row, "VendedorCodigo", "seller_id")
                ),
            }
        )
    return rows


def _map_customer_row(row: Mapping[str, Any]) -> dict[str, Any] | None:
    if not row_is_active(value_by_suffix(row, "Habilitado", "active")):
        return None
    customer_id = trim_code(
        value_by_suffix(row, "Cliente_Codigo", "id", "customer_code")
    )
    if not customer_id:
        return None
    return {
        "id": customer_id,
        "name": _text(value_by_suffix(row, "RazonSocial", "name")),
        "identification": canonicalize_cuit(
            value_by_suffix(row, "CUIT", "identification", "NroDocumento")
        ),
        "customer_code": customer_id,
        "active": True,
    }


# Real `Saldos al dia` rows: every key is `<generated prefix><alias>`.
_DEBT_ALIASES = {
    "tipo": "CVETCO_COD",
    "punto": "CVE_CODPVT",
    "letra": "CVE_LETRA",
    "numero": "CVE_NRO",
    "cliente": "CVE_CODCLI",
    "vendedor": "CVEVEN_COD",
    "emision": "CVE_FEMISION",
    "vencimiento": "CVE_FVTO",
    "importe": "CVE_IMPMONLOC",
    "saldo": "CVE_SALDOMONLOC",
}
_AMBIGUOUS = object()


def _resolve_debt_keys(keys: Iterable[Any]) -> dict[str, Any]:
    """Map each alias to the one key ending with it; ambiguous stays unusable."""
    resolved: dict[str, Any] = {}
    for name, alias in _DEBT_ALIASES.items():
        matches = [key for key in keys if str(key).endswith(alias)]
        if len(matches) == 1:
            resolved[name] = matches[0]
        elif matches:
            resolved[name] = _AMBIGUOUS
        else:
            resolved[name] = None
    return resolved


def _float(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _debt_row_entry(
    row: Mapping[str, Any],
    quotation_kinds: Any,
    cache: dict[tuple[Any, ...], dict[str, Any]],
) -> dict[str, Any] | None:
    shape = tuple(row)
    keys = cache.get(shape)
    if keys is None:
        keys = cache[shape] = _resolve_debt_keys(shape)
    if _AMBIGUOUS in keys.values():
        return None

    def cell(name: str) -> Any:
        key = keys[name]
        return None if key is None else row.get(key)

    balance = _float(cell("saldo"))
    if balance <= 0:
        return None
    tipo = _text(cell("tipo"))
    punto = _text(cell("punto"))
    letra = _text(cell("letra"))
    numero = _text(cell("numero"))
    customer_code = trim_code(cell("cliente"))
    if not (tipo and numero and customer_code):
        return None
    human_number = "-".join(part for part in (punto, numero) if part)
    return {
        "external_invoice_id": "|".join((tipo, punto, letra, numero)),
        "number": " ".join(part for part in (tipo, letra, human_number) if part),
        "customer_code": customer_code,
        "seller_code": trim_code(cell("vendedor")),
        "issue_date": _date(cell("emision")),
        "due_date": _date(cell("vencimiento")),
        "amount": _money(cell("importe")),
        "balance": round(balance, 2),
        "document_kind": document_kind(tipo, quotation_kinds),
    }


def map_debt_row(
    row: Mapping[str, Any], quotation_kinds: Any = None
) -> dict[str, Any] | None:
    """Open-debt entry for one real `Saldos al dia` row, or None when not open."""
    return _debt_row_entry(row, quotation_kinds, {})


def map_open_debt(
    payload: Any,
    quotation_kinds: Any = None,
    customer_code: Any = None,
    customer_codes: Iterable[str] | None = None,
) -> list[dict[str, Any]]:
    """Open entries (balance > 0); first id wins.

    ``customer_code`` keeps one customer, ``customer_codes`` keeps only those
    normalized codes (the enabled customers being cached).
    """
    wanted = trim_code(customer_code) if customer_code is not None else None
    allowed = None if customer_codes is None else frozenset(customer_codes)
    cache: dict[tuple[Any, ...], dict[str, Any]] = {}
    entries: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in as_rows(payload):
        entry = _debt_row_entry(row, quotation_kinds, cache)
        if entry is None:
            continue
        if wanted is not None and entry["customer_code"] != wanted:
            continue
        if allowed is not None and entry["customer_code"] not in allowed:
            continue
        if entry["external_invoice_id"] in seen:
            continue
        seen.add(entry["external_invoice_id"])
        entries.append(entry)
    return entries


def debt_state(due_date: Any, today: date | str | None) -> str:
    """`overdue` only when the ISO due date is strictly before today."""
    due = _text(due_date)
    if not due or today is None:
        return "open"
    today_iso = today.isoformat() if isinstance(today, date) else str(today)
    return "overdue" if due < today_iso else "open"


def entry_to_invoice(
    entry: Mapping[str, Any], today: date | str | None
) -> dict[str, Any]:
    """Sqlite-raw invoice row (collection `_format_customer_debt` input)."""
    return {
        "id": entry["external_invoice_id"],
        "number": entry["number"],
        "issue_date": entry["issue_date"],
        "due_date": entry["due_date"],
        "amount": entry["amount"],
        "balance": entry["balance"],
        "state": debt_state(entry["due_date"], today),
        "document_kind": entry["document_kind"],
    }
