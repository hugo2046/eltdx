from __future__ import annotations

from datetime import datetime

import pytest

from eltdx.mcp_tools import get_kline_data, get_quote_data
from eltdx.models import KlineItem, KlineResponse, Quote
from eltdx.protocol.unit import SHANGHAI_TZ


def _make_response(close_price_milli: int = 11280) -> KlineResponse:
    return KlineResponse(
        count=1,
        items=[
            KlineItem(
                time=datetime(2026, 5, 11, 15, 0, tzinfo=SHANGHAI_TZ),
                open_price=11.2,
                open_price_milli=11200,
                high_price=11.3,
                high_price_milli=11300,
                low_price=11.1,
                low_price_milli=11100,
                close_price=close_price_milli / 1000,
                close_price_milli=close_price_milli,
                last_close_price=11.2,
                last_close_price_milli=11200,
                volume=100,
                amount=112800.0,
                amount_milli=112800000,
            )
        ],
    )


class _FakeClient:
    instances: list[_FakeClient] = []

    def __init__(self, **kwargs) -> None:
        self.kwargs = kwargs
        self.calls: list[tuple] = []
        self.instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def get_kline(self, *args, **kwargs):
        self.calls.append(("get_kline", args, kwargs))
        return _make_response()

    def get_adjusted_kline(self, *args, **kwargs):
        self.calls.append(("get_adjusted_kline", args, kwargs))
        return _make_response(11330)

    def get_quote(self, *args, **kwargs):
        self.calls.append(("get_quote", args, kwargs))
        return [
            Quote(
                exchange="sz",
                code="000001",
                active1=0,
                active2=0,
                server_time_raw=15331973,
                server_time=datetime(2026, 5, 12, 15, 33, 19, 730000, tzinfo=SHANGHAI_TZ),
                last_price=11.28,
                last_price_milli=11280,
                open_price=11.2,
                open_price_milli=11200,
                high_price=11.3,
                high_price_milli=11300,
                low_price=11.1,
                low_price_milli=11100,
                last_close_price=11.2,
                last_close_price_milli=11200,
                total_hand=1000,
                current_hand=10,
                amount=100000.0,
                inside_dish=1,
                outer_disc=2,
                buy_levels=[],
                sell_levels=[],
                rate=0.7,
            )
        ]


@pytest.fixture(autouse=True)
def reset_fake_client() -> None:
    _FakeClient.instances = []


def test_get_kline_data_returns_jsonable_payload(monkeypatch) -> None:
    monkeypatch.setattr("eltdx.mcp_tools.TdxClient", _FakeClient)

    parsed = get_kline_data("sz000001", "day", start=2, count=3, kind="stock", timeout=5.0, probe_hosts=True)

    assert parsed["code"] == "sz000001"
    assert parsed["period"] == "day"
    assert parsed["kind"] == "stock"
    assert parsed["adjust"] is None
    assert parsed["start"] == 2
    assert parsed["request_count"] == 3
    assert parsed["count"] == 1
    assert parsed["items"][0]["time"] == "2026-05-11T15:00:00+08:00"
    assert parsed["items"][0]["close_price_milli"] == 11280

    client = _FakeClient.instances[0]
    assert client.kwargs == {"host": None, "timeout": 5.0, "pool_size": 1, "probe_hosts": True}
    assert client.calls == [
        ("get_kline", ("sz000001", "day"), {"start": 2, "count": 3, "kind": "stock", "include_raw": False})
    ]


def test_get_kline_data_uses_adjusted_kline(monkeypatch) -> None:
    monkeypatch.setattr("eltdx.mcp_tools.TdxClient", _FakeClient)

    parsed = get_kline_data("sz000001", "day", adjust=" QFQ ", count=5)

    assert parsed["adjust"] == "qfq"
    assert parsed["items"][0]["close_price_milli"] == 11330
    assert _FakeClient.instances[0].calls == [
        ("get_adjusted_kline", ("day", "sz000001"), {"adjust": "qfq", "start": 0, "count": 5, "include_raw": False})
    ]


def test_get_kline_data_rejects_invalid_adjust() -> None:
    with pytest.raises(ValueError, match="adjust must be"):
        get_kline_data("sz000001", "day", adjust="bad")


def test_get_kline_data_rejects_adjusted_index(monkeypatch) -> None:
    monkeypatch.setattr("eltdx.mcp_tools.TdxClient", _FakeClient)

    with pytest.raises(ValueError, match="adjusted kline only supports"):
        get_kline_data("sh000001", "day", kind="index", adjust="qfq")

    assert _FakeClient.instances == []


def test_get_quote_data_returns_jsonable_payload(monkeypatch) -> None:
    monkeypatch.setattr("eltdx.mcp_tools.TdxClient", _FakeClient)

    parsed = get_quote_data("sz000001, sh600000", timeout=5.0, pool_size=3, probe_hosts=True)

    assert parsed["codes"] == ["sz000001", "sh600000"]
    assert parsed["request_count"] == 2
    assert parsed["count"] == 1
    assert parsed["quotes"][0]["server_time"] == "2026-05-12T15:33:19.730000+08:00"
    assert parsed["quotes"][0]["last_price_milli"] == 11280

    client = _FakeClient.instances[0]
    assert client.kwargs == {"host": None, "timeout": 5.0, "pool_size": 3, "probe_hosts": True}
    assert client.calls == [("get_quote", (["sz000001", "sh600000"],), {})]


def test_get_quote_data_rejects_empty_codes() -> None:
    with pytest.raises(ValueError, match="at least one code"):
        get_quote_data(" , ")
