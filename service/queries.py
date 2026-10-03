# Copyright 2026 Seedian
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

"""Queries circuit: ObtenerJsonQueryVista only."""

from __future__ import annotations

import json
from typing import Any, Protocol

from .errors import BejermanTransportError


class Executor(Protocol):
    def execute(
        self, circuito: str, operacion: str, parametros_json: Any = None
    ) -> Any: ...


CIRCUITO = "QUERIES"


class QueriesOperations:
    def __init__(self, client: Executor) -> None:
        self._client = client

    def obtener_json_query_vista(
        self,
        escenario: str,
        vista: str,
        filtros: list[Any] | dict[str, Any] | str | None = None,
    ) -> Any:
        params: list[Any] = [escenario, vista]
        if filtros is not None:
            if isinstance(filtros, str):
                params.append(filtros)
            else:
                params.append(json.dumps(filtros))
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
