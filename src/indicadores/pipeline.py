"""ETL: extrai do Banco Central, transforma em DataFrame e carrega nos CSVs, de forma incremental."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from .bcb import BCBClient
from .series import SERIES, Serie
from .storage import CsvStore

DEFAULT_START = date(2010, 1, 1)
# Rebaixa alguns dias para pegar revisões e dados publicados com atraso.
OVERLAP_DAYS = 45


@dataclass
class UpdateResult:
    key: str
    start: date
    fetched: int
    added: int


def update_serie(
    serie: Serie, client: BCBClient, store: CsvStore, *, today: date, full_start: date = DEFAULT_START
) -> UpdateResult:
    last = store.last_date(serie.key)
    start = full_start if last is None else max(full_start, last - timedelta(days=OVERLAP_DAYS))
    df = client.fetch(serie, start, today)
    added = store.upsert(serie.key, df)
    return UpdateResult(serie.key, start, len(df), added)


def update_all(
    client: BCBClient, store: CsvStore, *, today: date | None = None, keys: list[str] | None = None
) -> list[UpdateResult]:
    today = today or date.today()
    return [update_serie(SERIES[key], client, store, today=today) for key in (keys or list(SERIES))]
