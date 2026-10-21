"""Armazena cada série em um CSV versionado no repositório (diffs pequenos a cada atualização)."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd


class CsvStore:
    def __init__(self, directory: Path) -> None:
        self.directory = directory

    def path(self, key: str) -> Path:
        return self.directory / f"{key}.csv"

    def load(self, key: str) -> pd.DataFrame:
        path = self.path(key)
        if not path.exists():
            return pd.DataFrame({"date": pd.Series(dtype="datetime64[ns]"), "value": pd.Series(dtype="float64")})
        return pd.read_csv(path, parse_dates=["date"])

    def last_date(self, key: str) -> date | None:
        df = self.load(key)
        return None if df.empty else df["date"].max().date()

    def upsert(self, key: str, new: pd.DataFrame) -> int:
        """Mescla novas observações; valores revisados substituem os antigos. Retorna quantas linhas entraram."""
        current = self.load(key)
        merged = pd.concat([current, new], ignore_index=True)
        merged = merged.drop_duplicates("date", keep="last").sort_values("date", ignore_index=True)
        self.directory.mkdir(parents=True, exist_ok=True)
        merged.to_csv(self.path(key), index=False, date_format="%Y-%m-%d")
        return len(merged) - len(current)
