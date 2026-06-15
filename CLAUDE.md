# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目定位

`eltdx` 是通达信在线行情协议的 Python 客户端库，零运行时依赖（`dependencies = []`）。提供 A 股行情、分时、成交明细、K 线、竞价、公司信息、F10 题材资料，并可作为 MCP 工具服务。仅供个人学习与协议研究，禁止商业用途。

## 常用命令

```bash
# 源码开发安装（先装到当前虚拟环境，否则 python -m eltdx 可能导入 site-packages 旧包）
pip install -e .[dev]          # 含 build、pytest
pip install -e .[mcp]          # 含 mcp，启用 eltdx-mcp

# 测试（默认离线，使用 InMemoryTransport，无需联网）
python -m pytest
python -m pytest tests/test_client.py            # 单个文件
python -m pytest tests/test_client.py::test_xxx  # 单个用例
python -m pytest -q                              # CI 用的精简输出

# 构建发布包
python -m build

# 命令行入口（安装后可用）
eltdx-smoke --help        # 对真实 7709 行情主站做联网冒烟检查
eltdx-f10-smoke --help    # 对 7615 F10 网关做联网检查
eltdx-mcp                 # 启动 MCP stdio 工具服务（占用终端）
```

**联网说明**：`tests/` 全部离线运行。需要打真实服务器的脚本在 `scripts/smoke/` 和 `scripts/validation/` 下，以及 `eltdx-smoke` / `eltdx-f10-smoke` 入口——这些会连接外网行情主站，不要在 CI 或无网环境跑。

CI（`.github/workflows/ci.yml`）在 Python 3.10–3.13 矩阵上跑 `pytest` + `build`。代码须兼容 3.10。

## 架构

分层职责（详见 `docs/ARCHITECTURE.md`）：

| 层 | 目录 | 职责 |
| --- | --- | --- |
| 产品入口 | `client.py` | `TdxClient` 门面，挂载各业务 API（`client.quotes`、`client.bars` 等） |
| 业务 API | `api/` | 面向使用者的方法，每个 API 继承 `ApiBase` |
| 协议层 | `protocol/` | 二进制帧、命令注册表、各命令的 builder/parser |
| 传输层 | `transport/` | socket 连接、重连、心跳、收包、请求执行 |
| 模型层 | `models/` | 对外返回的 dataclass 数据结构 |
| F10 | `f10/` | 独立的 7615 HTTP/JSON 网关客户端 |

### 双协议设计（关键）

`TdxClient` 同时挂载两套互不相关的协议栈：

1. **7709 二进制 TCP**（行情）：`api/` → `transport/` → `protocol/`。
2. **7615 HTTP/JSON**（F10 资料）：`client.f10`（`f10/client.py`）用 `urllib` 直接打 `http://static.tdx.com.cn:7615/TQLEX`，与上面的 socket 栈完全独立。

### 命令注册表是核心间接层

`protocol/commands/registry.py` 的 `COMMANDS` 字典把人类可读命令名映射到二进制命令号。调用链：

```
client.quotes.get_snapshots(...)         # 业务方法
  → ApiBase._execute("snapshots", ...)   # api/base.py
  → command_code("snapshots") → 0x054c   # registry 查表
  → transport.execute(0x054c, payload)
  → protocol/commands/quotes.py 的 builder/parser
  → models/quote.py
```

**新增协议命令的标准路径**：在 `registry.py` 注册 `CommandSpec`（命令号、所属模块、方法名）→ 在 `protocol/commands/<模块>.py` 写 builder/parser → 在 `api/<模块>.py` 暴露业务方法 → 在 `models/` 定义返回结构。业务层永远不直接写命令号。

### Transport 选择

- `TdxClient()` / `TdxClient.from_hosts()`：真实连接，默认 `PooledSocketTransport` 包 `SocketTransport`（连接池 + round-robin）。单 socket 内部有 reader 线程、30 秒后台心跳（`0x0004`）、pending 响应配对、push 队列（用于 `0x0547` 增量推送）。
- `TdxClient.in_memory()`：`InMemoryTransport`，固定 API 形状、供测试和示例用。**测试一律走这个。**
- 不传 `host`/`hosts` 时主站列表读包内 `src/eltdx/tdx_server.json`，不可用则退回代码内置列表。`probe_hosts=True` 会先 TCP 测速排序主站。

### 复权与衍生计算

K 线复权、换手率等派生计算放在 `equity.py`（`apply_factors_to_kline` 等），由 `client.py` 在返回前调用，不污染协议解析层。`helpers/` 提供跨命令组合的常用场景（股票信息汇总、概念板块成分等）。

## 文档地图

`docs/` 下文档是协议与字段的权威来源：`METHOD_REFERENCE.md`（方法与返回字段）、`API_REFERENCE.md`（完整 API）、`FIELD_REFERENCE.md`（字段总表）、`COMMANDS_7709.md`（命令号清单）、`F10_7615.md`（F10）、`MCP.md`（MCP 工具）、`ARCHITECTURE.md`（架构）。改协议或字段时同步更新对应文档。
