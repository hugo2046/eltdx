# MCP 工具

`eltdx` 提供 MCP 服务，方便在支持 MCP 的客户端里直接调用行情、K 线、F10 和题材相关工具。支持两种运行方式：

- **stdio**（`eltdx-mcp`）：本地使用，默认不鉴权。
- **HTTP**（`eltdx-mcp-http` / FastAPI 部署）：远程使用，支持静态 token 鉴权，并按 JSONL 记录每次调用的 `client_id` 与来源 IP。

## 启动

安装后运行：

```bash
pip install "eltdx[mcp]"
eltdx-mcp
```

也可以在源码目录运行：

```bash
pip install -e ".[mcp]"
eltdx-mcp
```

未安装到当前 Python 环境时，需要让 Python 找到 `src/` 目录：

PowerShell：

```powershell
$env:PYTHONPATH = "src"
python -m eltdx.mcp
```

bash：

```bash
PYTHONPATH=src python -m eltdx.mcp
```

`eltdx-mcp` 默认走 stdio，不开启 HTTP 端口；远程访问见下一节。

## HTTP 服务与鉴权

远程提供服务时使用 HTTP（Streamable HTTP）传输，并通过静态 token 鉴权。

### 配置 token

token 通过环境变量 `ELTDX_MCP_TOKENS` 配置，取值为 JSON 对象，**不要写进代码或提交到仓库**。键是 token 字符串，值是 `client_id` 简写或完整 claims：

```bash
# 简写：值即 client_id
export ELTDX_MCP_TOKENS='{"<给alice的随机串>":"alice","<给bob的随机串>":"bob"}'

# 完整写法：自定义 scopes
export ELTDX_MCP_TOKENS='{"<token>":{"client_id":"alice","scopes":["read"]}}'
```

客户端连接时需带 `Authorization: Bearer <token>`。stdio（`eltdx-mcp`）未配置 token 时免鉴权，方便本地使用；**HTTP 入口强制要求 token，未配置 `ELTDX_MCP_TOKENS` 会直接拒绝启动**，避免裸奔。

### 启动

```bash
# FastMCP 内置服务器，适合开发 / 简单部署
eltdx-mcp-http                       # 默认监听 127.0.0.1:8000

# FastAPI + uvicorn，适合正式部署
uvicorn eltdx.mcp:create_app --factory --host 0.0.0.0 --port 8000
```

`uvicorn` 方式下 MCP 端点挂在 `/mcp` 路径。

| 环境变量 | 说明 | 默认值 |
| --- | --- | --- |
| `ELTDX_MCP_TOKENS` | 静态 token 配置（JSON）；HTTP 入口必填，未配置则拒绝启动 | 无 |
| `ELTDX_MCP_ALLOWED_HOSTS` | 允许调用方自定义的 7709 主站白名单（逗号分隔）；HTTP 下未配置则禁止任何自定义 `host`，回退服务器默认主站 | 无 |
| `ELTDX_MCP_TRUST_PROXY` | 置为 `1`/`true` 时信任 `X-Forwarded-For`（仅当部署在可信反向代理后） | 关闭 |
| `ELTDX_MCP_HOST` | `eltdx-mcp-http` 监听地址 | `127.0.0.1` |
| `ELTDX_MCP_PORT` | `eltdx-mcp-http` 监听端口 | `8000` |
| `ELTDX_MCP_LOG` | JSONL 访问日志路径 | `logs/mcp_access.jsonl` |

### 访问日志

每次工具调用写一行 JSON，便于做安全统计（`pd.read_json(path, lines=True)`）：

```json
{"time": "2026-06-15T16:17:23+08:00", "tool": "eltdx_quote", "client_id": "alice", "peer_ip": "203.0.113.5", "ip": "203.0.113.5", "status": "ok"}
```

`peer_ip` 始终是 socket 真实对端地址；`ip` 仅在 `ELTDX_MCP_TRUST_PROXY` 开启时才采信 `X-Forwarded-For` 首段，否则等于 `peer_ip`。存在转发头时还会记录原始 `forwarded_for` 供审计。

> ⚠️ 安全提醒：
> - 部署务必置于 **HTTPS** 之后——静态 token 是明文 Bearer，HTTP 明文传输会被中间人截获。
> - `host` 参数经 HTTP 暴露存在 SSRF 风险，默认已禁止调用方自定义；确需放开时用 `ELTDX_MCP_ALLOWED_HOSTS` 白名单按主站精确放行。
> - 只有部署在可信代理（如自管 nginx）后才开 `ELTDX_MCP_TRUST_PROXY`，否则 `X-Forwarded-For` 可被客户端伪造。

## 工具列表

| 工具 | 作用 |
| --- | --- |
| `eltdx_quote` | 查询一个或多个股票的行情快照 |
| `eltdx_kline` | 查询 K 线 / 周期线，支持复权参数 |
| `eltdx_stock_profile` | 汇总股票表头信息，合并行情、代码表和财务基础信息 |
| `eltdx_stock_topics` | 查询某只股票的全部题材 / 概念板块 |
| `eltdx_topic_stocks` | 查询某个题材 / 概念板块里的股票 |
| `eltdx_company_profile` | 查询 F10 公司概况 |
| `eltdx_hot_topics` | 查询 F10 热点题材明细 |
| `eltdx_auction_0925` | 查询指定日期 09:25 竞价成交快照 |
| `eltdx_docs_index` | 返回项目主要文档入口 |

## 调用示例

查询行情：

```json
{
  "codes": ["sz000001", "sh600000"],
  "timeout": 3
}
```

查询 K 线：

```json
{
  "code": "sz000001",
  "period": "day",
  "count": 120,
  "adjust": "qfq"
}
```

查询个股题材：

```json
{
  "code": "000034",
  "timeout": 3
}
```

查询题材成分股：

```json
{
  "seed_code": "000034",
  "topic_name": "存储芯片",
  "sort_by": "zdf"
}
```

## 连接参数

| 参数 | 说明 |
| --- | --- |
| `timeout` | 请求超时时间，默认 `8.0` 秒 |
| `host` | 指定单个 `7709` 主站，例如 `"116.205.183.150:7709"` |

F10 工具走 `7615/TQLEX` HTTP 网关，不需要 7709 握手。
