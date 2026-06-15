"""MCP server entry for eltdx.

提供两种运行方式：

- ``main()`` —— 本地 stdio（与旧版一致，默认不鉴权）。
- ``http_main()`` / ``create_app()`` —— HTTP（Streamable HTTP），支持静态
  token 鉴权，并把每次工具调用按 JSONL 记录调用者 ``client_id`` 与来源 IP。

静态 token 通过环境变量 ``ELTDX_MCP_TOKENS`` 配置（JSON），不入代码库。
"""

from __future__ import annotations

import json
import os
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from .client import TdxClient
from .serialization import to_jsonable

DEFAULT_HTTP_HOST = "127.0.0.1"
DEFAULT_HTTP_PORT = 8000
DEFAULT_LOG_PATH = "logs/mcp_access.jsonl"

# 防止 create_mcp_server 多次调用时重复挂载 JSONL sink。
_ACCESS_SINK_ID: int | None = None

# HTTP 入口启用后置 True：限制工具调用者自定义 host，避免 SSRF。
# stdio 本地使用保持 False（调用者即本机用户，无信任边界）。
_HOST_RESTRICTED: bool = False


def quote(codes: str | Sequence[str], *, timeout: float = 8.0, host: str | None = None) -> Any:
    """Query quote snapshots."""

    with _client(timeout=timeout, host=host) as client:
        return _json(client.get_quote(codes))


def kline(
    code: str,
    *,
    period: str = "day",
    count: int = 120,
    start: int = 0,
    adjust: str | None = None,
    anchor_date: str | int | None = None,
    timeout: float = 8.0,
    host: str | None = None,
) -> Any:
    """Query K-line data."""

    with _client(timeout=timeout, host=host) as client:
        return _json(
            client.get_kline(
                period,
                code,
                start=start,
                count=count,
                adjust=adjust,
                anchor_date=anchor_date,
            )
        )


def stock_profile(codes: str | Sequence[str], *, timeout: float = 8.0, host: str | None = None) -> Any:
    """Return quote, code-table and finance fields in one table."""

    with _client(timeout=timeout, host=host) as client:
        return _json(client.helpers.stock_profile_table(codes))


def stock_topics(code: str, *, timeout: float = 8.0) -> Any:
    """Query all known topics for one stock."""

    client = TdxClient(timeout=timeout, heartbeat_interval=None)
    return _json(client.helpers.stock_topics(code))


def topic_stocks(
    seed_code: str,
    *,
    topic_id: str | int | None = None,
    topic_name: str | None = None,
    sort_by: str = "zdf",
    timeout: float = 8.0,
) -> Any:
    """Query stocks inside one topic."""

    client = TdxClient(timeout=timeout, heartbeat_interval=None)
    return _json(client.helpers.topic_stocks(seed_code, topic_id=topic_id, topic_name=topic_name, sort_by=sort_by))


def company_profile(code: str, *, timeout: float = 8.0) -> Any:
    """Query F10 company profile."""

    client = TdxClient(timeout=timeout, heartbeat_interval=None)
    return _json(client.f10.company_profile(code))


def hot_topics(code: str, *, timeout: float = 8.0) -> Any:
    """Query F10 hot-topic detail rows."""

    client = TdxClient(timeout=timeout, heartbeat_interval=None)
    return _json(client.f10.hot_topics(code))


def auction_0925(
    code: str,
    trading_date,
    *,
    timeout: float = 8.0,
    host: str | None = None,
    max_pages: int | None = 100,
) -> Any:
    """Query the 09:25 auction final tick from historical trade details."""

    with _client(timeout=timeout, host=host) as client:
        return _json(client.get_auction_0925(code, trading_date, max_pages=max_pages))


def docs_index() -> dict[str, str]:
    """Return local documentation entry points."""

    return {
        "README": "README.md",
        "API": "docs/API_REFERENCE.md",
        "methods": "docs/METHOD_REFERENCE.md",
        "fields": "docs/FIELD_REFERENCE.md",
        "7709_commands": "docs/COMMANDS_7709.md",
        "F10": "docs/F10_7615.md",
        "helpers": "docs/helpers/README.md",
    }


def _load_tokens() -> dict[str, dict[str, Any]]:
    """从环境变量 ``ELTDX_MCP_TOKENS`` 读取静态 token 配置。

    取值为 JSON 对象，键是 token 字符串，值是 ``client_id`` 简写或完整 claims::

        {"<token>": "alice"}
        {"<token>": {"client_id": "alice", "scopes": ["read"]}}

    :returns: token 到 claims 的映射；未配置时返回空字典（即不启用鉴权，
        便于本地 stdio 直接使用）。
    """

    raw = os.environ.get("ELTDX_MCP_TOKENS")
    if not raw:
        return {}
    data = json.loads(raw)
    tokens: dict[str, dict[str, Any]] = {}
    for token, value in data.items():
        claims: dict[str, Any] = {"client_id": value} if isinstance(value, str) else dict(value)
        claims.setdefault("scopes", ["read"])
        tokens[token] = claims
    return tokens


def _check_host(host: str | None) -> str | None:
    """校验工具调用者传入的 ``host``，防止经 HTTP 暴露后被用于 SSRF。

    stdio 本地使用（``_HOST_RESTRICTED`` 为 False）时调用者即本机用户，直接放行。
    HTTP 暴露时仅放行 ``ELTDX_MCP_ALLOWED_HOSTS``（逗号分隔）白名单内的主站；
    未配置白名单则拒绝任何自定义 host，回退服务器默认主站列表。

    :param host: 调用方请求的 7709 主站，``None`` 表示用服务器默认。
    :returns: 校验通过的 host（或 ``None``）。
    :raises ValueError: HTTP 下传入了不在白名单内的 host。
    """

    if host is None or not _HOST_RESTRICTED:
        return host
    allowed = {h.strip() for h in os.environ.get("ELTDX_MCP_ALLOWED_HOSTS", "").split(",") if h.strip()}
    if host not in allowed:
        raise ValueError(f"host {host!r} 不在 ELTDX_MCP_ALLOWED_HOSTS 白名单内")
    return host


def _trust_proxy() -> bool:
    """是否信任 ``X-Forwarded-For``（仅当部署在可信反向代理之后才应开启）。"""

    return os.environ.get("ELTDX_MCP_TRUST_PROXY", "").strip().lower() in {"1", "true", "yes", "on"}


def _resolve_ips(request) -> dict[str, str]:
    """解析来源 IP，区分 socket 真实对端与可伪造的转发头。

    默认记录 socket ``peer_ip``；仅当 ``ELTDX_MCP_TRUST_PROXY`` 开启时才用
    ``X-Forwarded-For`` 首段作为 ``ip``。原始转发头始终留痕以便审计。

    :param request: Starlette ``Request`` 对象。
    :returns: 含 ``peer_ip`` / ``ip`` 及（存在时）``forwarded_for`` 的字段字典。
    """

    peer_ip = request.client.host if request.client else "unknown"
    forwarded = request.headers.get("x-forwarded-for")
    fields = {"peer_ip": peer_ip}
    if forwarded:
        fields["forwarded_for"] = forwarded  # 原始头留痕，不可信但可审计
    # X-Forwarded-For 是 "client, proxy1, proxy2"，仅在可信代理后首段才是真实客户端。
    fields["ip"] = forwarded.split(",")[0].strip() if (forwarded and _trust_proxy()) else peer_ip
    return fields


def _configure_access_log():
    """配置 JSONL 访问日志 sink（幂等），返回绑定后的 loguru logger。"""

    global _ACCESS_SINK_ID
    from loguru import logger

    if _ACCESS_SINK_ID is None:
        log_path = Path(os.environ.get("ELTDX_MCP_LOG", DEFAULT_LOG_PATH))
        log_path.parent.mkdir(parents=True, exist_ok=True)

        def _jsonl_sink(message) -> None:
            record = message.record
            payload = {"time": record["time"].isoformat()}
            payload.update({k: v for k, v in record["extra"].items() if k != "eltdx_access"})
            with log_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(payload, ensure_ascii=False) + "\n")

        _ACCESS_SINK_ID = logger.add(
            _jsonl_sink,
            level="INFO",
            enqueue=True,  # 跨线程安全，工具调用走后台线程时不丢日志
            filter=lambda r: r["extra"].get("eltdx_access") is True,
        )
    return logger.bind(eltdx_access=True)


def _build_access_middleware():
    """构建按工具调用记录 client_id 与来源 IP 的中间件。"""

    from fastmcp.server.dependencies import get_access_token, get_http_request
    from fastmcp.server.middleware import Middleware, MiddlewareContext

    access_logger = _configure_access_log()

    class AccessLogMiddleware(Middleware):
        async def on_call_tool(self, context: MiddlewareContext, call_next):
            token = get_access_token()
            client_id = token.client_id if token is not None else "anonymous"
            fields = {"tool": context.message.name, "client_id": client_id}
            try:
                fields.update(_resolve_ips(get_http_request()))
            except RuntimeError:
                fields["ip"] = "stdio"  # stdio 传输下没有 HTTP 请求上下文
            try:
                result = await call_next(context)
            except Exception as exc:  # 失败也要留痕，便于安全统计
                access_logger.bind(**fields, status="error", error=repr(exc)).info("tool_call")
                raise
            access_logger.bind(**fields, status="ok").info("tool_call")
            return result

    return AccessLogMiddleware()


def create_mcp_server(*, require_auth: bool = False):
    """Create the FastMCP server.

    :param require_auth: 为 ``True`` 时，未配置 ``ELTDX_MCP_TOKENS`` 则直接拒绝
        创建（避免 HTTP 入口在忘记配置 token 时静默裸奔）。stdio 入口保持
        ``False`` 以便本地免鉴权使用。
    :raises RuntimeError: ``require_auth`` 为真但没有可用 token。
    """

    try:
        from fastmcp import FastMCP
    except ImportError as exc:  # pragma: no cover - depends on optional package install
        raise RuntimeError("MCP support requires the optional 'mcp' extra. Install with: pip install 'eltdx[mcp]'") from exc

    auth = None
    tokens = _load_tokens()
    if tokens:
        from fastmcp.server.auth.providers.jwt import StaticTokenVerifier

        auth = StaticTokenVerifier(tokens=tokens, required_scopes=["read"])
    elif require_auth:
        raise RuntimeError(
            "HTTP MCP 服务要求鉴权：请在环境变量 ELTDX_MCP_TOKENS 配置静态 token（JSON）后再启动。"
        )

    server = FastMCP("eltdx", instructions="eltdx A-share quote, K-line, F10 and topic data tools.", auth=auth)
    server.add_middleware(_build_access_middleware())
    server.tool(name="eltdx_quote")(quote)
    server.tool(name="eltdx_kline")(kline)
    server.tool(name="eltdx_stock_profile")(stock_profile)
    server.tool(name="eltdx_stock_topics")(stock_topics)
    server.tool(name="eltdx_topic_stocks")(topic_stocks)
    server.tool(name="eltdx_company_profile")(company_profile)
    server.tool(name="eltdx_hot_topics")(hot_topics)
    server.tool(name="eltdx_auction_0925")(auction_0925)
    server.tool(name="eltdx_docs_index")(docs_index)
    return server


def create_app():
    """构建用于部署的 FastAPI 应用，把 MCP 挂在 ``/mcp`` 路径下。

    通过 ``uvicorn eltdx.mcp:create_app --factory`` 运行；部署务必置于
    HTTPS 之后，否则静态 token 会以明文传输。强制要求配置 token。

    :returns: 已挂载 MCP 子应用的 FastAPI 实例。
    """

    global _HOST_RESTRICTED
    from fastapi import FastAPI

    _HOST_RESTRICTED = True
    mcp_app = create_mcp_server(require_auth=True).http_app(path="/")
    app = FastAPI(title="eltdx-mcp", lifespan=mcp_app.lifespan)
    app.mount("/mcp", mcp_app)
    return app


def main() -> int:
    """Run the MCP server over stdio."""

    create_mcp_server().run("stdio")
    return 0


def http_main() -> int:
    """以 HTTP（Streamable HTTP）运行 MCP 服务。

    监听地址通过 ``ELTDX_MCP_HOST`` / ``ELTDX_MCP_PORT`` 配置；强制要求配置 token。
    """

    global _HOST_RESTRICTED
    _HOST_RESTRICTED = True
    host = os.environ.get("ELTDX_MCP_HOST", DEFAULT_HTTP_HOST)
    port = int(os.environ.get("ELTDX_MCP_PORT", DEFAULT_HTTP_PORT))
    create_mcp_server(require_auth=True).run(transport="http", host=host, port=port)
    return 0


def _client(*, timeout: float, host: str | None) -> TdxClient:
    return TdxClient(host=_check_host(host), timeout=timeout, heartbeat_interval=None)


def _json(value: Any) -> Any:
    return to_jsonable(value)


if __name__ == "__main__":
    raise SystemExit(main())
