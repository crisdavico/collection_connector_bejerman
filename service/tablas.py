# Copyright 2026 Seedian
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

"""Tablas circuit: ObtenerClientes only."""

from __future__ import annotations

from typing import Any, Protocol


class Executor(Protocol):
    def execute(
        self, circuit: str, operation: str, parameters_json: Any = None
    ) -> Any: ...


CIRCUITO = "TABLAS"


class TablasOperations:
    def __init__(self, client: Executor) -> None:
        self._client = client

    def get_customers(self) -> Any:
        # The live ERP refuses `{}` for this operation and accepts `[]`.
        return self._client.execute(CIRCUITO, "ObtenerClientes", [])
