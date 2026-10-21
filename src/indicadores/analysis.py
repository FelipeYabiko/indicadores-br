"""Transformações de séries temporais usadas no dashboard."""

from __future__ import annotations

import pandas as pd


def to_series(df: pd.DataFrame) -> pd.Series:
    return df.set_index("date")["value"].sort_index()


def monthly_last(series: pd.Series) -> pd.Series:
    """Último valor de cada mês, indexado pelo primeiro dia do mês."""
    return series.resample("MS").last().dropna()


def accumulated(monthly_pct: pd.Series, months: int = 12) -> pd.Series:
    """Variação acumulada em janelas móveis: juros compostos, não soma simples."""
    factors = 1 + monthly_pct / 100
    return ((factors.rolling(months).apply(lambda w: w.prod(), raw=True) - 1) * 100).dropna()


def real_interest(selic: pd.Series, ipca_monthly: pd.Series) -> pd.DataFrame:
    """Juro real ex-post: Selic deflacionada pelo IPCA acumulado em 12 meses (equação de Fisher)."""
    df = pd.DataFrame({"selic": monthly_last(selic), "ipca_12m": accumulated(ipca_monthly)}).dropna()
    df["juro_real"] = ((1 + df["selic"] / 100) / (1 + df["ipca_12m"] / 100) - 1) * 100
    return df


def pct_change_over(series: pd.Series, periods: int) -> pd.Series:
    return (series.pct_change(periods=periods, fill_method=None) * 100).dropna()


def snapshot(series: pd.Series, lookback: pd.DateOffset | None = None) -> dict[str, float | pd.Timestamp | None]:
    """Valor mais recente e a diferença para o valor de `lookback` atrás (padrão: 1 ano)."""
    lookback = lookback or pd.DateOffset(years=1)
    clean = series.dropna().sort_index()
    if clean.empty:
        return {"date": None, "value": None, "delta": None}
    last_date = clean.index[-1]
    previous = clean[: last_date - lookback]
    delta = float(clean.iloc[-1] - previous.iloc[-1]) if not previous.empty else None
    return {"date": last_date, "value": float(clean.iloc[-1]), "delta": delta}
