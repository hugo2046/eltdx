from __future__ import annotations

import asyncio
import sys
import types
from dataclasses import dataclass

from eltdx.mcp_server import create_server


@dataclass(slots=True)
class _FakeTool:
    name: str
    description: str | None


class _FakeFastMCP:
    def __init__(self, name: str) -> None:
        self.name = name
        self._tools: list[_FakeTool] = []

    def tool(self, *, name: str):
        def decorator(fn):
            self._tools.append(_FakeTool(name=name, description=fn.__doc__))
            return fn

        return decorator

    async def list_tools(self) -> list[_FakeTool]:
        return self._tools


def test_mcp_server_registers_kline_and_quote_tools(monkeypatch) -> None:
    fastmcp_module = types.ModuleType("mcp.server.fastmcp")
    fastmcp_module.FastMCP = _FakeFastMCP
    monkeypatch.setitem(sys.modules, "mcp", types.ModuleType("mcp"))
    monkeypatch.setitem(sys.modules, "mcp.server", types.ModuleType("mcp.server"))
    monkeypatch.setitem(sys.modules, "mcp.server.fastmcp", fastmcp_module)

    async def run() -> list[str]:
        server = create_server()
        tools = await server.list_tools()
        return sorted(tool.name for tool in tools)

    assert asyncio.run(run()) == ["tdx_get_kline", "tdx_get_quote"]

