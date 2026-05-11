from __future__ import annotations

from typing import Any

from .adjustment import normalize_adjust_mode
from .client import TdxClient
from .serialization import to_jsonable


def _normalize_codes(codes: str | list[str] | tuple[str, ...]) -> list[str]:
    if isinstance(codes, str):
        return [item.strip() for item in codes.split(",") if item.strip()]
    return [str(item).strip() for item in codes if str(item).strip()]


def _normalize_adjust(adjust: str | None) -> str | None:
    if adjust is None:
        return None
    text = str(adjust).strip()
    if not text or text.lower() == "none":
        return None
    try:
        return normalize_adjust_mode(text).value
    except ValueError as exc:
        raise ValueError("adjust must be one of: none, qfq, hfq") from exc


def get_kline_data(
    code: str,
    period: str = "day",
    *,
    start: int = 0,
    count: int = 200,
    kind: str = "stock",
    adjust: str | None = None,
    include_raw: bool = False,
    host: str | None = None,
    timeout: float = 8.0,
    pool_size: int = 1,
    probe_hosts: bool = False,
) -> dict[str, Any]:
    normalized_adjust = _normalize_adjust(adjust)
    if normalized_adjust is not None and kind != "stock":
        raise ValueError("adjusted kline only supports kind='stock'")

    with TdxClient(host=host, timeout=timeout, pool_size=pool_size, probe_hosts=probe_hosts) as client:
        if normalized_adjust is None:
            response = client.get_kline(code, period, start=start, count=count, kind=kind, include_raw=include_raw)
        else:
            response = client.get_adjusted_kline(period, code, adjust=normalized_adjust, start=start, count=count, include_raw=include_raw)

    payload = to_jsonable(response)
    return {
        "code": code,
        "period": period,
        "kind": kind,
        "adjust": normalized_adjust,
        "start": start,
        "request_count": count,
        "count": payload["count"],
        "items": payload["items"],
        "raw_frame_hex": payload.get("raw_frame_hex"),
        "raw_payload_hex": payload.get("raw_payload_hex"),
    }


def get_quote_data(
    codes: str | list[str] | tuple[str, ...],
    *,
    host: str | None = None,
    timeout: float = 8.0,
    pool_size: int = 2,
    probe_hosts: bool = False,
) -> dict[str, Any]:
    code_list = _normalize_codes(codes)
    if not code_list:
        raise ValueError("at least one code is required")

    with TdxClient(host=host, timeout=timeout, pool_size=pool_size, probe_hosts=probe_hosts) as client:
        quotes = client.get_quote(code_list)

    payload = to_jsonable(quotes)
    return {
        "codes": code_list,
        "request_count": len(code_list),
        "count": len(payload),
        "quotes": payload,
    }
