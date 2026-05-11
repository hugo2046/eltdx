from __future__ import annotations

from unittest.mock import Mock

import pytest

from eltdx.client import TdxClient


class _FakeConnection:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.connect_calls = 0
        self.close_calls = 0

    def connect(self) -> None:
        self.connect_calls += 1
        if self.fail:
            raise RuntimeError("connect failed")

    def close(self) -> None:
        self.close_calls += 1


def test_client_context_manager_connects_and_closes() -> None:
    client = TdxClient()
    client.connect = Mock()
    client.close = Mock()

    with client as current:
        assert current is client

    client.connect.assert_called_once_with()
    client.close.assert_called_once_with()


def test_client_rotates_default_hosts_across_connection_pool() -> None:
    client = TdxClient(hosts=["a:7709", "b:7709", "c:7709"], pool_size=3)

    assert client._hosts == ["a:7709", "b:7709", "c:7709"]
    assert client._connections[0]._hosts == ["a:7709", "b:7709", "c:7709"]
    assert client._connections[1]._hosts == ["b:7709", "c:7709", "a:7709"]
    assert client._connections[2]._hosts == ["c:7709", "a:7709", "b:7709"]


def test_client_can_probe_and_sort_hosts_before_building_connections(monkeypatch) -> None:
    monkeypatch.setattr("eltdx.client.sort_hosts_by_latency", lambda hosts, timeout, max_workers: ["b:7709", "a:7709"])

    client = TdxClient(hosts=["a:7709", "b:7709"], pool_size=2, probe_hosts=True)

    assert client._hosts == ["b:7709", "a:7709"]
    assert client._connections[0]._hosts == ["b:7709", "a:7709"]
    assert client._connections[1]._hosts == ["a:7709", "b:7709"]


def test_client_connect_closes_pool_when_one_connection_fails() -> None:
    first = _FakeConnection()
    second = _FakeConnection(fail=True)
    third = _FakeConnection()
    client = TdxClient(hosts=["a:7709"], pool_size=1)
    client._connections = [first, second, third]

    with pytest.raises(RuntimeError, match="connect failed"):
        client.connect()

    assert first.connect_calls == 1
    assert second.connect_calls == 1
    assert third.connect_calls == 0
    assert first.close_calls == 1
    assert second.close_calls == 1
    assert third.close_calls == 1
    assert client._executor is None
    assert client._connected is False
