"""Cliente da API de dados abertos do Banco Central (SGS)."""

from __future__ import annotations

import time
from datetime import date, datetime, timedelta

import httpx
import pandas as pd

from .series import Serie

BASE_URL = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{code}/dados"
# A API recusa janelas maiores que 10 anos em séries diárias; usamos 5 para ter folga.
WINDOW_YEARS = 5
RETRYABLE_STATUS = {429, 500, 502, 503, 504}


class BCBError(RuntimeError):
    pass


class BCBClient:
    def __init__(self, client: httpx.Client | None = None, retries: int = 3, backoff: float = 1.0) -> None:
        self._client = client or httpx.Client(timeout=30.0, headers={"Accept": "application/json"})
        self._retries = retries
        self._backoff = backoff

    def fetch(self, serie: Serie, start: date, end: date) -> pd.DataFrame:
        """Busca observações entre `start` e `end` (inclusive), em janelas, e devolve date/value."""
        frames = [self._fetch_window(serie, a, b) for a, b in _windows(start, end, WINDOW_YEARS)]
        frames = [f for f in frames if not f.empty]
        if not frames:
            return pd.DataFrame({"date": pd.Series(dtype="datetime64[ns]"), "value": pd.Series(dtype="float64")})
        df = pd.concat(frames, ignore_index=True)
        # A série da meta Selic já traz datas futuras (até a próxima reunião do Copom).
        df = df[df["date"] <= pd.Timestamp(end)]
        return df.drop_duplicates("date").sort_values("date", ignore_index=True)

    def _fetch_window(self, serie: Serie, start: date, end: date) -> pd.DataFrame:
        params = {"formato": "json", "dataInicial": _br(start), "dataFinal": _br(end)}
        payload = self._get_json(BASE_URL.format(code=serie.code), params)
        return pd.DataFrame(
            {
                "date": pd.to_datetime([row["data"] for row in payload], format="%d/%m/%Y"),
                "value": pd.to_numeric([row["valor"] for row in payload]),
            }
        )

    def _get_json(self, url: str, params: dict[str, str]) -> list[dict[str, str]]:
        for attempt in range(self._retries + 1):
            try:
                response = self._client.get(url, params=params)
            except httpx.TransportError as exc:
                error: Exception = exc
            else:
                # Janela sem dados volta como 404 com corpo de erro; tratamos como lista vazia.
                if response.status_code == 404:
                    return []
                if response.status_code not in RETRYABLE_STATUS:
                    response.raise_for_status()
                    return response.json()
                error = BCBError(f"HTTP {response.status_code} em {url}")
            if attempt < self._retries:
                time.sleep(self._backoff * 2**attempt)  # backoff exponencial: 1s, 2s, 4s...
        raise BCBError(f"Falha ao consultar {url} após {self._retries + 1} tentativas") from error


def _windows(start: date, end: date, years: int) -> list[tuple[date, date]]:
    windows = []
    current = start
    while current <= end:
        window_end = min(_add_years(current, years) - timedelta(days=1), end)
        windows.append((current, window_end))
        current = window_end + timedelta(days=1)
    return windows


def _add_years(day: date, years: int) -> date:
    try:
        return day.replace(year=day.year + years)
    except ValueError:  # 29 de fevereiro em ano não bissexto
        return day.replace(year=day.year + years, day=28)


def _br(day: date) -> str:
    return datetime(day.year, day.month, day.day).strftime("%d/%m/%Y")
