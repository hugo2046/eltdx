from __future__ import annotations

import json
from datetime import date, datetime

import pytest

from eltdx import Exchange, KlineItem, KlineResponse, Quote, QuoteLevel, to_json, to_jsonable
from eltdx.protocol.unit import SHANGHAI_TZ


def _make_kline_response() -> KlineResponse:
    return KlineResponse(
        count=1,
        items=[
            KlineItem(
                time=datetime(2026, 5, 11, 15, 0, tzinfo=SHANGHAI_TZ),
                open_price=11.1,
                open_price_milli=11100,
                high_price=11.3,
                high_price_milli=11300,
                low_price=11.0,
                low_price_milli=11000,
                close_price=11.28,
                close_price_milli=11280,
                last_close_price=11.2,
                last_close_price_milli=11200,
                volume=100,
                amount=112800.0,
                amount_milli=112800000,
            )
        ],
    )


def test_to_jsonable_converts_nested_dataclasses_and_datetimes() -> None:
    parsed = to_jsonable(_make_kline_response())

    assert parsed == {
        "count": 1,
        "items": [
            {
                "time": "2026-05-11T15:00:00+08:00",
                "open_price": 11.1,
                "open_price_milli": 11100,
                "high_price": 11.3,
                "high_price_milli": 11300,
                "low_price": 11.0,
                "low_price_milli": 11000,
                "close_price": 11.28,
                "close_price_milli": 11280,
                "last_close_price": 11.2,
                "last_close_price_milli": 11200,
                "volume": 100,
                "amount": 112800.0,
                "amount_milli": 112800000,
                "order_count": None,
                "up_count": None,
                "down_count": None,
            }
        ],
        "raw_frame_hex": None,
        "raw_payload_hex": None,
    }


def test_to_jsonable_converts_quote_levels() -> None:
    quote = Quote(
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
        buy_levels=[QuoteLevel(True, 11.27, 11270, 100)],
        sell_levels=[QuoteLevel(False, 11.29, 11290, 200)],
        rate=0.7,
    )

    parsed = to_jsonable(quote)

    assert parsed["server_time"] == "2026-05-12T15:33:19.730000+08:00"
    assert parsed["buy_levels"] == [{"buy": True, "price": 11.27, "price_milli": 11270, "number": 100}]
    assert parsed["sell_levels"] == [{"buy": False, "price": 11.29, "price_milli": 11290, "number": 200}]


def test_to_jsonable_converts_common_containers_dates_and_enums() -> None:
    parsed = to_jsonable({"exchange": Exchange.SZ, "days": [date(2026, 5, 12)]})

    assert parsed == {"exchange": "sz", "days": ["2026-05-12"]}


def test_to_json_outputs_json_string() -> None:
    text = to_json(_make_kline_response())

    parsed = json.loads(text)

    assert parsed["items"][0]["time"] == "2026-05-11T15:00:00+08:00"


def test_to_jsonable_rejects_unknown_objects() -> None:
    class Unknown:
        pass

    with pytest.raises(TypeError, match="Unknown"):
        to_jsonable(Unknown())

