# Copyright 2026 Seedian
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

"""Queries circuit: ObtenerJsonQueryVista only."""

from __future__ import annotations

import json
from typing import Any, Protocol

from .errors import BejermanTransportError


class Executor(Protocol):
    def execute(
        self, circuit: str, operation: str, parameters_json: Any = None
    ) -> Any: ...


CIRCUITO = "QUERIES"


class QueriesOperations:
    def __init__(self, client: Executor) -> None:
        self._client = client

    def get_json_query_view(
        self,
        scenario: str,
        view: str,
        filters: list[Any] | dict[str, Any] | str | None = None,
    ) -> Any:
        params: list[Any] = [scenario, view]
        if filters is not None:
            if isinstance(filters, str):
                params.append(filters)
            else:
                params.append(json.dumps(filters))
        result = self._client.execute(CIRCUITO, "ObtenerJsonQueryVista", params)
        if isinstance(result, str):
            # Query views answer a JSON string that itself holds the JSON rows.
            try:
                return json.loads(result)
            except json.JSONDecodeError:
                raise BejermanTransportError(
                    "Query payload is not valid JSON"
                ) from None
        return result
