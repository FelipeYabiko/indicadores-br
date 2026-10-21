from datetime import date

import httpx
import pytest

from indicadores.bcb import BCBClient, BCBError, _windows
from indicadores.series import SERIES


def make_client(handler) -> BCBClient:
    # MockTransport intercepta as requisições: nenhum teste acessa a internet.
    return BCBClient(httpx.Client(transport=httpx.MockTransport(handler)), backoff=0)


def test_parses_dates_and_decimal_values():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["dataInicial"] == "01/01/2026"
        return httpx.Response(
            200, json=[{"data": "02/01/2026", "valor": "5.4321"}, {"data": "05/01/2026", "valor": "5.5"}]
        )

    df = make_client(handler).fetch(SERIES["dolar"], date(2026, 1, 1), date(2026, 1, 31))

    assert df["date"].dt.strftime("%Y-%m-%d").tolist() == ["2026-01-02", "2026-01-05"]
    assert df["value"].tolist() == [5.4321, 5.5]


def test_splits_long_periods_into_windows():
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append((request.url.params["dataInicial"], request.url.params["dataFinal"]))
        return httpx.Response(200, json=[])

    make_client(handler).fetch(SERIES["dolar"], date(2010, 1, 1), date(2026, 6, 30))

    assert seen == [
        ("01/01/2010", "31/12/2014"),
        ("01/01/2015", "31/12/2019"),
        ("01/01/2020", "31/12/2024"),
        ("01/01/2025", "30/06/2026"),
    ]


def test_not_found_means_no_data():
    df = make_client(lambda request: httpx.Response(404, json={"erro": {}})).fetch(
        SERIES["ipca"], date(2026, 10, 2), date(2026, 10, 21)
    )
    assert df.empty


def test_drops_future_dates():
    payload = [{"data": "20/10/2026", "valor": "13.75"}, {"data": "10/12/2026", "valor": "13.75"}]
    df = make_client(lambda request: httpx.Response(200, json=payload)).fetch(
        SERIES["selic"], date(2026, 10, 1), date(2026, 10, 21)
    )
    assert len(df) == 1


def test_retries_transient_errors():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        if len(calls) < 3:
            return httpx.Response(502)
        return httpx.Response(200, json=[{"data": "01/09/2026", "valor": "0.82"}])

    df = make_client(handler).fetch(SERIES["ipca"], date(2026, 9, 1), date(2026, 9, 30))

    assert len(calls) == 3
    assert df["value"].tolist() == [0.82]


def test_gives_up_after_retries():
    with pytest.raises(BCBError):
        make_client(lambda request: httpx.Response(503)).fetch(SERIES["ipca"], date(2026, 9, 1), date(2026, 9, 30))


def test_does_not_retry_client_errors():
    with pytest.raises(httpx.HTTPStatusError):
        make_client(lambda request: httpx.Response(400)).fetch(SERIES["ipca"], date(2026, 9, 1), date(2026, 9, 30))


def test_windows_handle_leap_day():
    assert _windows(date(2024, 2, 29), date(2030, 1, 1), 5)[0] == (date(2024, 2, 29), date(2029, 2, 27))
