from __future__ import annotations

import json
import socket
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from importlib import resources
from typing import Any


SERVER_FILE = "tdx_server.json"
DEFAULT_PROBE_TIMEOUT = 1.2
DEFAULT_PROBE_WORKERS = 32


@dataclass(frozen=True, slots=True)
class HostProbeResult:
    host: str
    ok: bool
    latency_ms: float | None = None
    error: str | None = None


def normalize_host(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    host = value.strip()
    if not host or ":" not in host:
        return None

    address, port = host.rsplit(":", 1)
    address = address.strip()
    port = port.strip()
    if not address or not port.isdigit():
        return None
    return f"{address}:{int(port)}"


def unique_hosts(values: list[Any] | tuple[Any, ...]) -> list[str]:
    hosts: list[str] = []
    for value in values:
        host = normalize_host(value)
        if host is not None and host not in hosts:
            hosts.append(host)
    return hosts


def load_server_hosts() -> list[str]:
    data = load_server_config()
    hosts = data.get("hosts")
    if isinstance(hosts, list):
        return unique_hosts(hosts)

    values: list[Any] = [data.get("current_host")]
    for key in ("manual_hosts", "imported_hosts"):
        item = data.get(key, [])
        if isinstance(item, list):
            values.extend(item)
    return unique_hosts(values)


def load_server_config() -> dict[str, Any]:
    try:
        content = resources.files("eltdx").joinpath(SERVER_FILE).read_text(encoding="utf-8")
        data = json.loads(content)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}
    return data if isinstance(data, dict) else {}


def probe_host(host: str, *, timeout: float = DEFAULT_PROBE_TIMEOUT) -> HostProbeResult:
    normalized = normalize_host(host)
    if normalized is None:
        return HostProbeResult(host=str(host), ok=False, error="invalid host")

    address, port = normalized.rsplit(":", 1)
    started = time.perf_counter()
    try:
        with socket.create_connection((address, int(port)), timeout=timeout):
            latency_ms = round((time.perf_counter() - started) * 1000.0, 2)
            return HostProbeResult(host=normalized, ok=True, latency_ms=latency_ms)
    except OSError as exc:
        return HostProbeResult(host=normalized, ok=False, error=type(exc).__name__)


def probe_hosts(
    hosts: list[str] | tuple[str, ...],
    *,
    timeout: float = DEFAULT_PROBE_TIMEOUT,
    max_workers: int = DEFAULT_PROBE_WORKERS,
) -> list[HostProbeResult]:
    candidates = unique_hosts(list(hosts))
    if not candidates:
        return []

    worker_count = min(max(1, max_workers), len(candidates))
    results: list[HostProbeResult] = []
    with ThreadPoolExecutor(max_workers=worker_count, thread_name_prefix="eltdx-probe") as executor:
        futures = [executor.submit(probe_host, host, timeout=timeout) for host in candidates]
        for future in as_completed(futures):
            results.append(future.result())
    return results


def sort_hosts_by_latency(
    hosts: list[str] | tuple[str, ...],
    *,
    timeout: float = DEFAULT_PROBE_TIMEOUT,
    max_workers: int = DEFAULT_PROBE_WORKERS,
) -> list[str]:
    candidates = unique_hosts(list(hosts))
    results = probe_hosts(candidates, timeout=timeout, max_workers=max_workers)
    reachable = sorted(
        (result for result in results if result.ok),
        key=lambda result: (result.latency_ms if result.latency_ms is not None else float("inf"), candidates.index(result.host)),
    )
    unreachable = [host for host in candidates if host not in {result.host for result in reachable}]
    return [result.host for result in reachable] + unreachable


DEFAULT_HOSTS = load_server_hosts()
