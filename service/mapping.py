# Copyright 2026 Seedian
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

"""Suffix-map Bejerman TABLAS rows into sqlite raw shapes.

Only what every Bejerman install shares lives here: the TABLAS customer rows and
the debt state. The debt query views are particular to each customer and are
mapped by the addon of that customer's profile.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from typing import Any

from odoo.addons.collection.customer_match import matches_customer_query

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


def find_customer_rows(
    payload: Any,
    identification: Any,
) -> list[Mapping[str, Any]]:
    """Raw rows of every active customer this query may mean, of any seller.

    The customer master's seller never scopes them: the caller narrows them
    to its seller's customers and keeps only its seller's documents.
    ``identification`` may be the CUIT, the customer code, or the numeric tail
    of that code (``0160`` selects ``NS0160``).
    """
    matches = []
    for row in as_rows(payload):
        mapped = _map_customer_row(row)
        if mapped is None:
            continue
        if matches_customer_query(
            mapped["identification"], mapped["customer_code"], identification
        ):
            matches.append(row)
    return matches


def customer_from_row(row: Mapping[str, Any]) -> dict[str, Any] | None:
    """Sqlite-raw customer for a raw TABLAS row, or None when disabled."""
    return _map_customer_row(row)


def erp_customer_code(row: Mapping[str, Any]) -> str:
    """Customer code exactly as the ERP stores it (stripped, zeros kept)."""
    return _text(value_by_suffix(row, "Cliente_Codigo", "id", "customer_code"))


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


def debt_state(due_date: Any, today: date | str | None) -> str:
    """`overdue` only when the ISO due date is strictly before today."""
    due = _text(due_date)
    if not due or today is None:
        return "open"
    today_iso = today.isoformat() if isinstance(today, date) else str(today)
    return "overdue" if due < today_iso else "open"
