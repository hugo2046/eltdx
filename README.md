<div align="center">
  <h1>eltdx</h1>
  <p><strong>面向 A 股行情研究的通达信协议 Python SDK</strong></p>
  <p>
    用一个 <code>TdxClient</code> 读取快照、分时、逐笔、K 线、集合竞价、历史 <code>09:25</code> 竞价、代码表、股本变化和复权相关数据。
  </p>
  <p>
    <a href="https://pypi.org/project/eltdx/"><img alt="PyPI" src="https://img.shields.io/pypi/v/eltdx?label=pypi&logo=pypi"></a>
    <a href="https://pypi.org/project/eltdx/"><img alt="Python 3.10+" src="https://img.shields.io/badge/Python-3.10%2B-blue"></a>
    <a href="https://github.com/electkismet/eltdx/actions/workflows/ci.yml"><img alt="Build" src="https://img.shields.io/github/actions/workflow/status/electkismet/eltdx/ci.yml?branch=main&label=build"></a>
    <a href="https://github.com/electkismet/eltdx/blob/main/LICENSE"><img alt="License" src="https://img.shields.io/pypi/l/eltdx?label=license"></a>
  </p>
</div>

## 这是什么

`eltdx` 是一个轻量的通达信在线行情协议库，目标是让你用尽量少的代码拿到结构清楚、容易落库和分析的行情数据。它不要求安装通达信客户端，也不读取本地 `vipdoc`、`.day`、`.lc1` 这类文件。

它比较适合：

| 场景 | 适合程度 | 说明 |
| --- | --- | --- |
| 临时脚本查行情 | 很适合 | `with TdxClient() as client:` 一段代码就能跑完并自动断开 |
| 批量拉快照 | 适合 | `get_quote()` 内置分批，默认连接池会分发请求 |
| K 线落库或给 Agent 用 | 适合 | 提供 `get_kline()`、`get_kline_all()` 和 JSON-friendly 转换 |
| 集合竞价研究 | 适合 | 支持集合竞价序列和历史 `09:25` 快速提取 |
| 财报 / F10 / 公告解析 | 不覆盖 | 这不是财务数据下载和解析框架 |
| 本地通达信文件解析 | 不覆盖 | 暂不读取 `vipdoc`、`.day`、`.lc1` 等本地数据文件 |

主要定位是个人行情研究和开发调试，请勿用于任何商业或违法用途。

## 安装

```bash
python -m pip install eltdx
```

升级：

```bash
python -m pip install -U eltdx
```

从源码开发：

```bash
git clone https://github.com/electkismet/eltdx.git
cd eltdx
python -m pip install -e .
```

环境要求：Python `3.10+`。

## 快速开始

### 读取实时行情快照

```python
from eltdx import TdxClient

with TdxClient() as client:
    quotes = client.get_quote(["sz000001", "sh600000"])

for item in quotes:
    print(item.code, item.last_price, item.last_close_price, item.server_time)
```

### 读取 K 线并转成 JSON-friendly 结构

```python
from eltdx import TdxClient, to_jsonable

with TdxClient() as client:
    response = client.get_kline("sz000001", "day", count=5)

payload = to_jsonable(response)
print(payload["count"])
print(payload["items"][-1])
```

### 快速提取历史 `09:25` 竞价结果

```python
from eltdx import TdxClient

with TdxClient() as client:
    row = client.get_auction_0925("000001", "2026-04-09")

print(row.code, row.trading_date, row.has_auction_0925)
print(row.price, row.volume, row.amount)
```

## 能力概览

| 数据 | API | 返回模型 | 说明 |
| --- | --- | --- | --- |
| 行情快照 | `get_quote()` | `list[Quote]` | 最新价、昨收、今开、最高、最低、五档盘口、成交量额等 |
| 代码表 | `get_codes()` / `get_codes_all()` | `CodePage` / `list[SecurityCode]` | 沪深北代码表；注意不是纯股票列表 |
| 常用代码清单 | `get_a_share_codes_all()` / `get_etf_codes_all()` / `get_index_codes_all()` | `list[str]` | 对底层代码表做常用过滤 |
| 分时 | `get_minute()` / `get_history_minute()` | `MinuteResponse` | 实时分时和历史分时 |
| 逐笔 | `get_trades()` / `get_trades_all()` | `TradeResponse` | 实时逐笔、历史逐笔、自动翻页 |
| 历史 `09:25` | `get_auction_0925()` | `Auction0925Result` | 只定位目标交易日 `09:25` 那一笔，适合批量导出 |
| K 线 | `get_kline()` / `get_kline_all()` | `KlineResponse` | 支持分钟、日、周、月等周期 |
| 复权 K 线 | `get_adjusted_kline()` / `get_adjusted_kline_all()` | `KlineResponse` | 支持 `qfq` / `hfq` |
| 集合竞价 | `get_call_auction()` | `CallAuctionResponse` | 集合竞价阶段序列 |
| 公司行为 / 股本 | `get_gbbq()` / `get_xdxr()` / `get_equity()` / `get_factors()` | 多种 dataclass | 股本变化、除权除息、复权因子等 |

返回值默认是 dataclass，不是随手拼的裸 `dict`。时间字段会尽量转成 Python 原生 `date` / `datetime`，价格字段通常同时保留浮点值和 `*_milli` 整数值，方便展示和精确计算同时使用。

## 服务器选择

`eltdx` 内置了一个 `tdx_server.json`，默认服务器列表已经按本机 TCP 连接测速结果由快到慢排序。普通使用不需要手动传服务器。

```python
from eltdx import TdxClient

with TdxClient() as client:
    print(client.get_quote("sz000001")[0].last_price)
```

如果你想按当前网络重新测速，可以在初始化时打开 `probe_hosts=True`。测速只发生在创建 client 时，不会每次请求都测速。

```python
from eltdx import TdxClient

with TdxClient(probe_hosts=True, probe_timeout=1.2) as client:
    print(client.get_quote("sz000001")[0].last_price)
```

也可以完全指定自己的服务器列表：

```python
from eltdx import TdxClient

hosts = ["116.205.183.150:7709", "116.205.171.132:7709"]

with TdxClient(hosts=hosts, pool_size=2, timeout=8.0) as client:
    print(client.get_quote(["sz000001", "sh600000"]))
```

| 参数 | 默认值 | 说明 |
| --- | --- | --- |
| `host` | `None` | 单个服务器地址，适合临时指定 |
| `hosts` | `None` | 多个服务器地址，优先级高于 `host` |
| `pool_size` | `2` | 连接池大小；批量快照会分发到不同连接 |
| `batch_size` | `80` | `get_quote()` 自动分批大小，上限会限制在 `80` |
| `probe_hosts` | `False` | 初始化时是否对候选服务器测速并重排 |
| `probe_timeout` | `1.2` | 单个服务器测速超时秒数 |

## MCP 工具

`eltdx` 带了一个最小 MCP server，适合把行情查询交给支持 MCP 的 Agent 或本地工具。它是一个服务，里面可以有多个工具；当前先暴露 K 线和快照两个工具。

安装 MCP 依赖：

```bash
python -m pip install "eltdx[mcp]"
```

启动：

```bash
eltdx-mcp
```

| 工具名 | 作用 | 常用参数 |
| --- | --- | --- |
| `tdx_get_kline` | 读取一页 A 股 K 线，返回 JSON-friendly `dict` | `code`, `period`, `start`, `count`, `kind`, `adjust`, `probe_hosts` |
| `tdx_get_quote` | 读取一只或多只证券的实时行情快照 | `codes`, `timeout`, `pool_size`, `probe_hosts` |

普通安装 `eltdx` 不会安装 MCP SDK；只有安装 `eltdx[mcp]` 时才会引入 MCP 依赖。

## 常见注意事项

### 代码要不要带市场前缀？

推荐带完整前缀，例如 `sz000001`、`sh600000`、`bj920001`。部分接口可以自动补前缀，但明确写出来更少歧义。

### `get_count("sh")` 为什么很大？

它返回的是通达信代码表条目数，不是“上海市场股票总数”。如果你要股票口径，优先用：

| 需求 | 推荐 API |
| --- | --- |
| A 股数量 | `get_a_share_count(exchange)` |
| 股票类数量，含 B 股等 | `get_stock_count(exchange)` |
| A 股代码列表 | `get_a_share_codes_all()` |
| ETF 代码列表 | `get_etf_codes_all()` |
| 指数代码列表 | `get_index_codes_all()` |

### `get_codes()` 为什么不全是股票？

因为它读的是底层代码表，里面可能混有股票、指数、ETF、基金、债券回购、板块分类项等。需要更干净的清单时，用上面那些过滤 helper。

### 这个库是不是只服务 A 股？

项目核心是通达信在线行情协议下的沪深北市场数据，主要服务 A 股行情研究；同时也能按接口能力读取代码表里的指数、ETF 等条目。它不是港美股行情库，也不是财报、F10、公告或本地文件解析框架。

### 什么时候用 `with TdxClient()`？

临时脚本推荐用 `with`，代码块结束自动关闭连接。长连接服务可以手动 `connect()` / `close()`：

```python
from eltdx import TdxClient

client = TdxClient(pool_size=2)
client.connect()
try:
    quotes = client.get_quote(["sz000001", "sh600000"])
finally:
    client.close()
```

### 怎么看原始协议数据？

支持 `include_raw=True` 的接口会返回原始十六进制字段，适合排查协议解析问题。

```python
from eltdx import TdxClient

with TdxClient() as client:
    minute = client.get_minute("sz000001", include_raw=True)
    print(minute.raw_frame_hex)
    print(minute.raw_payload_hex)
```

## 文档地图

| 文档 | 适合谁看 | 内容 |
| --- | --- | --- |
| [docs/README.md](docs/README.md) | 第一次进项目的人 | 文档导航 |
| [docs/API_REFERENCE.md](docs/API_REFERENCE.md) | 查参数和返回值的人 | 完整 API 用法 |
| [docs/EXAMPLES.md](docs/EXAMPLES.md) | 想直接复制代码的人 | 常见任务示例 |
| [docs/FIELD_REFERENCE.md](docs/FIELD_REFERENCE.md) | 需要理解字段的人 | 字段含义和口径 |
| [docs/DEBUG_GUIDE.md](docs/DEBUG_GUIDE.md) | 排查连接或协议问题的人 | raw 数据、服务器和常见问题 |
| [scripts/README.md](scripts/README.md) | 想跑脚本的人 | smoke / validation 脚本说明 |

## 开发与验证

```bash
python -m pip install -e ".[dev]"
python -m pytest tests\unit
python -m build
```

联网集成测试需要真实通达信行情服务器，可按需开启：

```bash
set ELTDX_RUN_LIVE=1
python -m pytest tests\integration
```

## 项目参考

- 感谢 [injoyai/tdx](https://github.com/injoyai/tdx) 的启发。

## 联系方式

- QQ 群：[点击链接加入群聊](https://qm.qq.com/q/zAjpZsvfzy)
- 邮箱：`dapaoxixixi@163.com`

## 许可证

MIT
