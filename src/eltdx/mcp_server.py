from __future__ import annotations

from typing import Any

from .mcp_tools import get_kline_data, get_quote_data


def create_server():
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as exc:
        raise RuntimeError("Install MCP support with: python -m pip install 'eltdx[mcp]'") from exc

    server = FastMCP("eltdx")

    @server.tool(name="tdx_get_kline")
    def tdx_get_kline(
        code: str,
        period: str = "day",
        start: int = 0,
        count: int = 200,
        kind: str = "stock",
        adjust: str | None = None,
        include_raw: bool = False,
        timeout: float = 8.0,
        probe_hosts: bool = False,
    ) -> dict[str, Any]:
        """Fetch one page of A-share K-line data from TDX-compatible quote servers."""
        return get_kline_data(
            code,
            period,
            start=start,
            count=count,
            kind=kind,
            adjust=adjust,
            include_raw=include_raw,
            timeout=timeout,
            probe_hosts=probe_hosts,
        )

    @server.tool(name="tdx_get_quote")
    def tdx_get_quote(
        codes: str,
        timeout: float = 8.0,
        pool_size: int = 2,
        probe_hosts: bool = False,
    ) -> dict[str, Any]:
        """Fetch realtime A-share quote snapshots for one or more comma-separated codes."""
        return get_quote_data(codes, timeout=timeout, pool_size=pool_size, probe_hosts=probe_hosts)

    return server


def main() -> None:
    create_server().run()


if __name__ == "__main__":
    main()
