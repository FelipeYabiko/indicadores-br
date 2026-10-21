"""Catálogo das séries do SGS (Sistema Gerenciador de Séries Temporais) do Banco Central."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class Serie:
    key: str
    code: int
    name: str
    unit: str
    frequency: Literal["diaria", "mensal"]


SERIES: dict[str, Serie] = {
    s.key: s
    for s in [
        Serie("selic", 432, "Meta Selic", "% a.a.", "diaria"),
        Serie("ipca", 433, "IPCA", "% no mês", "mensal"),
        Serie("igpm", 189, "IGP-M", "% no mês", "mensal"),
        Serie("dolar", 1, "Dólar (PTAX venda)", "R$/US$", "diaria"),
    ]
}
