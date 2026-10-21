"""Dashboard Streamlit. Rode com: streamlit run app.py"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

# Permite rodar o app sem instalar o pacote (ex.: no Streamlit Community Cloud).
sys.path.insert(0, str(Path(__file__).parent / "src"))

from indicadores import analysis  # noqa: E402
from indicadores.series import SERIES  # noqa: E402
from indicadores.storage import CsvStore  # noqa: E402

DATA_DIR = Path(__file__).parent / "data"
COLORS = {
    "selic": "#2563eb",
    "ipca": "#dc2626",
    "ipca_12m": "#dc2626",
    "igpm": "#d97706",
    "juro_real": "#059669",
    "dolar": "#7c3aed",
}

st.set_page_config(page_title="Indicadores BR", page_icon="📈", layout="wide")


@st.cache_data(ttl=3600)
def load() -> dict[str, pd.Series]:
    store = CsvStore(DATA_DIR)
    return {key: analysis.to_series(store.load(key)) for key in SERIES}


def fmt(value: float | None, suffix: str = "%", decimals: int = 2) -> str:
    if value is None:
        return "-"
    return f"{value:,.{decimals}f}".replace(",", "X").replace(".", ",").replace("X", ".") + suffix


def line_chart(df: pd.DataFrame, columns: dict[str, str], y_title: str):
    data = df[list(columns)].rename(columns=columns).reset_index(names="data")
    long = data.melt(id_vars="data", var_name="série", value_name="valor")
    color_map = {label: COLORS[key] for key, label in columns.items()}
    fig = px.line(long, x="data", y="valor", color="série", color_discrete_map=color_map)
    fig.update_layout(yaxis_title=y_title, xaxis_title=None, legend_title=None, hovermode="x unified", height=420)
    return fig


series = load()
if all(s.empty for s in series.values()):
    st.error("Sem dados. Rode `indicadores atualizar` para baixar as séries.")
    st.stop()

st.title("📈 Indicadores econômicos do Brasil")
st.caption("Fonte: Banco Central do Brasil (SGS). Os dados são atualizados todo dia por um workflow do GitHub Actions.")

first_year = min(s.index.min().year for s in series.values() if not s.empty)
start_year, end_year = st.sidebar.slider(
    "Período", min_value=first_year, max_value=date.today().year, value=(date.today().year - 10, date.today().year)
)
window = slice(pd.Timestamp(start_year, 1, 1), pd.Timestamp(end_year, 12, 31))

real = analysis.real_interest(series["selic"], series["ipca"])
ipca_12m = analysis.accumulated(series["ipca"])
igpm_12m = analysis.accumulated(series["igpm"])
dolar_12m = analysis.pct_change_over(analysis.monthly_last(series["dolar"]), 12)

cols = st.columns(4)
# (coluna, rótulo, série, formato do valor, formato da variação). A variação precisa começar
# pelo sinal, porque o Streamlit decide a cor e a seta pelo "-" inicial.
cards = [
    (cols[0], "Meta Selic", series["selic"], "{}% a.a.", "{} p.p."),
    (cols[1], "IPCA 12 meses", ipca_12m, "{}%", "{} p.p."),
    (cols[2], "Juro real (ex-post)", real["juro_real"], "{}% a.a.", "{} p.p."),
    (cols[3], "Dólar PTAX", series["dolar"], "R$ {}", "{} R$"),
]
for col, label, s, value_fmt, delta_fmt in cards:
    snap = analysis.snapshot(s)
    decimals = 4 if label.startswith("Dólar") else 2
    col.metric(
        label,
        value_fmt.format(fmt(snap["value"], "", decimals)),
        delta=None if snap["delta"] is None else delta_fmt.format(fmt(snap["delta"], "", decimals)) + " em 12 meses",
        # Inflação subindo é ruim (seta vermelha); para os demais, subir ou cair não é bom nem ruim em si.
        delta_color="inverse" if label.startswith("IPCA") else "off",
        help=f"Última observação: {snap['date']:%d/%m/%Y}" if snap["date"] is not None else None,
    )

tab_juros, tab_inflacao, tab_dolar, tab_dados = st.tabs(["Juros", "Inflação", "Dólar", "Dados"])

with tab_juros:
    st.subheader("Selic, inflação e juro real")
    st.plotly_chart(
        line_chart(real[window], {"selic": "Selic", "ipca_12m": "IPCA 12m", "juro_real": "Juro real"}, "% a.a."),
    )
    st.caption("Juro real = (1 + Selic) / (1 + IPCA acumulado em 12 meses) - 1, no fim de cada mês.")

with tab_inflacao:
    st.subheader("Inflação acumulada em 12 meses")
    inflation = pd.DataFrame({"ipca": ipca_12m, "igpm": igpm_12m}).dropna()[window]
    st.plotly_chart(line_chart(inflation, {"ipca": "IPCA", "igpm": "IGP-M"}, "% em 12 meses"))

    st.subheader("Variação mensal")
    monthly = pd.DataFrame({"IPCA": series["ipca"], "IGP-M": series["igpm"]})[window].reset_index(names="mês")
    fig = px.bar(
        monthly.melt(id_vars="mês", var_name="índice", value_name="%"),
        x="mês",
        y="%",
        color="índice",
        barmode="group",
        color_discrete_map={"IPCA": COLORS["ipca"], "IGP-M": COLORS["igpm"]},
    )
    fig.update_layout(xaxis_title=None, legend_title=None, height=380)
    st.plotly_chart(fig)

with tab_dolar:
    st.subheader("Dólar PTAX (venda)")
    fig = px.line(series["dolar"][window].rename_axis("data").reset_index(), x="data", y="value")
    fig.update_traces(line_color=COLORS["dolar"])
    fig.update_layout(yaxis_title="R$/US$", xaxis_title=None, height=380)
    st.plotly_chart(fig)

    st.subheader("Variação em 12 meses")
    variation = dolar_12m[window].rename_axis("mês").reset_index()
    variation["sinal"] = variation["value"].map(lambda v: "alta" if v >= 0 else "queda")
    fig = px.bar(
        variation, x="mês", y="value", color="sinal", color_discrete_map={"alta": "#dc2626", "queda": "#059669"}
    )
    fig.update_layout(yaxis_title="%", xaxis_title=None, showlegend=False, height=320)
    st.plotly_chart(fig)

with tab_dados:
    key = st.selectbox("Série", list(SERIES), format_func=lambda k: f"{SERIES[k].name} ({SERIES[k].unit})")
    table = (
        series[key][window]
        .rename(SERIES[key].name)
        .rename_axis("data")
        .reset_index()
        .sort_values("data", ascending=False)
    )
    st.dataframe(table, hide_index=True)
    st.download_button("Baixar CSV", table.to_csv(index=False).encode(), file_name=f"{key}.csv", mime="text/csv")
