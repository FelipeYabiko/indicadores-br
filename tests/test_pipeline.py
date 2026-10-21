from datetime import date

import pandas as pd
import pytest

from indicadores import analysis
from indicadores.pipeline import OVERLAP_DAYS, update_serie
from indicadores.series import SERIES
from indicadores.storage import CsvStore


def frame(rows: dict[str, float]) -> pd.DataFrame:
    return pd.DataFrame({"date": pd.to_datetime(list(rows)), "value": list(rows.values())})


class FakeClient:
    def __init__(self, df: pd.DataFrame) -> None:
        self.df = df
        self.calls: list[tuple[date, date]] = []

    def fetch(self, serie, start, end):
        self.calls.append((start, end))
        return self.df


def test_upsert_merges_and_replaces_revised_values(tmp_path):
    store = CsvStore(tmp_path)
    assert store.upsert("ipca", frame({"2026-07-01": 0.2, "2026-08-01": -0.3})) == 2

    added = store.upsert("ipca", frame({"2026-08-01": -0.32, "2026-09-01": 0.82}))

    assert added == 1
    assert store.load("ipca")["value"].tolist() == [0.2, -0.32, 0.82]
    assert store.last_date("ipca") == date(2026, 9, 1)


def test_first_update_downloads_full_history(tmp_path):
    store = CsvStore(tmp_path)
    client = FakeClient(frame({"2010-01-04": 1.72}))

    result = update_serie(SERIES["dolar"], client, store, today=date(2026, 10, 21))

    assert client.calls == [(date(2010, 1, 1), date(2026, 10, 21))]
    assert result.added == 1


def test_next_update_is_incremental_with_overlap(tmp_path):
    store = CsvStore(tmp_path)
    store.upsert("dolar", frame({"2026-10-20": 5.01}))
    client = FakeClient(frame({"2026-10-20": 5.01, "2026-10-21": 5.02}))

    result = update_serie(SERIES["dolar"], client, store, today=date(2026, 10, 21))

    start, _ = client.calls[0]
    assert (date(2026, 10, 20) - start).days == OVERLAP_DAYS
    assert result.added == 1


def test_accumulated_uses_compound_interest():
    monthly = pd.Series([1.0] * 12, index=pd.date_range("2025-01-01", periods=12, freq="MS"))
    assert analysis.accumulated(monthly).iloc[-1] == pytest.approx(12.6825, abs=1e-4)


def test_real_interest_fisher_equation():
    months = pd.date_range("2025-01-01", periods=12, freq="MS")
    selic = pd.Series(13.75, index=pd.date_range("2025-01-01", "2025-12-31", freq="D"))
    ipca = pd.Series(0.4, index=months)

    real = analysis.real_interest(selic, ipca)

    ipca_12m = (1.004**12 - 1) * 100
    assert real["juro_real"].iloc[-1] == pytest.approx((1.1375 / (1 + ipca_12m / 100) - 1) * 100)


def test_snapshot_compares_with_one_year_before():
    series = pd.Series([10.0, 11.0, 12.0], index=pd.to_datetime(["2025-06-01", "2025-10-01", "2026-10-01"]))
    snap = analysis.snapshot(series)
    assert snap["value"] == 12.0
    assert snap["delta"] == 1.0
    assert analysis.snapshot(pd.Series(dtype=float))["value"] is None
