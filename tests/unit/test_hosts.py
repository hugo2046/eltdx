from __future__ import annotations

from eltdx import hosts


def test_default_hosts_loaded_from_server_file() -> None:
    config = hosts.load_server_config()

    assert config["schema_version"] == 1
    assert hosts.DEFAULT_HOSTS == hosts.unique_hosts(config["hosts"])
    assert len(hosts.DEFAULT_HOSTS) >= 10
    assert len(hosts.DEFAULT_HOSTS) == len(set(hosts.DEFAULT_HOSTS))
    assert all(":" in host for host in hosts.DEFAULT_HOSTS)


def test_unique_hosts_normalizes_and_deduplicates() -> None:
    parsed = hosts.unique_hosts([
        " 1.1.1.1:7709 ",
        "1.1.1.1:7709",
        "2.2.2.2:07709",
        "bad",
        None,
    ])

    assert parsed == ["1.1.1.1:7709", "2.2.2.2:7709"]


def test_sort_hosts_by_latency_keeps_unreachable_hosts_last(monkeypatch) -> None:
    results = [
        hosts.HostProbeResult("slow:7709", ok=True, latency_ms=20.0),
        hosts.HostProbeResult("down:7709", ok=False, error="timeout"),
        hosts.HostProbeResult("fast:7709", ok=True, latency_ms=3.0),
    ]

    monkeypatch.setattr(hosts, "probe_hosts", lambda candidates, timeout, max_workers: results)

    assert hosts.sort_hosts_by_latency(["slow:7709", "down:7709", "fast:7709"]) == [
        "fast:7709",
        "slow:7709",
        "down:7709",
    ]
