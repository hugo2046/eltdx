from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor

from eltdx.protocol.frame import RequestFrame, ResponseFrame
from eltdx.transport.heartbeat import HeartbeatLoop
from eltdx.transport.connection import TdxConnection
from eltdx.transport.reader import ResponseReader
from eltdx.transport.router import ResponseRouter


def _make_response(msg_id: int = 7) -> ResponseFrame:
    return ResponseFrame(
        control=0x1C,
        msg_id=msg_id,
        msg_type=0x0450,
        zip_length=0,
        length=0,
        data=b"",
        raw=b"",
    )


def test_response_router_registers_and_delivers() -> None:
    router = ResponseRouter()

    message_queue = router.register(7)
    response = _make_response(7)
    router.deliver(response)

    assert message_queue.get_nowait() == response

    router.unregister(7)
    router.clear()


def test_response_reader_decodes_and_routes(monkeypatch) -> None:
    stop_event = threading.Event()
    responses: list[ResponseFrame] = []
    errors: list[str] = []

    def on_response(response: ResponseFrame) -> None:
        responses.append(response)
        stop_event.set()

    def on_error() -> None:
        errors.append("error")

    monkeypatch.setattr("eltdx.transport.reader.read_response_frame", lambda sock: b"raw")
    monkeypatch.setattr("eltdx.transport.reader.decode_response", lambda raw: _make_response(11))

    reader = ResponseReader(stop_event, on_response, on_error)
    reader.run(object())

    assert [response.msg_id for response in responses] == [11]
    assert errors == []


def test_heartbeat_loop_sends_until_stopped() -> None:
    stop_event = threading.Event()
    sent: list[str] = []
    errors: list[str] = []

    def send_heartbeat() -> None:
        sent.append("tick")
        stop_event.set()

    def on_error() -> None:
        errors.append("error")

    heartbeat = HeartbeatLoop(stop_event, 0, send_heartbeat, lambda: True, on_error)
    heartbeat.run()

    assert sent == ["tick"]
    assert errors == []


def test_connection_serializes_requests_per_socket(monkeypatch) -> None:
    connection = TdxConnection(["127.0.0.1:7709"])
    entered_first_request = threading.Event()
    release_first_request = threading.Event()
    events: list[str] = []

    def fake_request(frame: RequestFrame, expected_type: int) -> ResponseFrame:
        events.append(f"request:{frame.msg_id}")
        if frame.msg_id == 1:
            entered_first_request.set()
            assert release_first_request.wait(timeout=2)
        return _make_response(frame.msg_id)

    monkeypatch.setattr(connection, "_request", fake_request)

    def call_request(label: str) -> int:
        response = connection._request_frame(
            lambda msg_id: events.append(f"build:{label}:{msg_id}") or RequestFrame(msg_id=msg_id, msg_type=0x0450),
            0x0450,
        )
        return response.msg_id

    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(call_request, "first")
        assert entered_first_request.wait(timeout=2)

        second = executor.submit(call_request, "second")
        assert "build:second:2" not in events

        release_first_request.set()

        assert first.result(timeout=2) == 1
        assert second.result(timeout=2) == 2

    assert events == ["build:first:1", "request:1", "build:second:2", "request:2"]


class _FakeSocket:
    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


class _FakeExecutor:
    def __init__(self) -> None:
        self.shutdown_calls: list[tuple[bool, bool]] = []

    def shutdown(self, *, wait: bool = True, cancel_futures: bool = False) -> None:
        self.shutdown_calls.append((wait, cancel_futures))


def test_stale_disconnect_callback_does_not_close_new_generation() -> None:
    connection = TdxConnection(["127.0.0.1:7709"])
    sock = _FakeSocket()
    executor = _FakeExecutor()
    connection._generation = 2
    connection._socket = sock
    connection._connected_host = "127.0.0.1:7709"
    connection._executor = executor

    connection._mark_disconnected(1)

    assert sock.closed is False
    assert connection.connected_host == "127.0.0.1:7709"
    assert executor.shutdown_calls == []


def test_current_disconnect_callback_closes_socket_and_executor() -> None:
    connection = TdxConnection(["127.0.0.1:7709"])
    sock = _FakeSocket()
    executor = _FakeExecutor()
    connection._generation = 2
    connection._socket = sock
    connection._connected_host = "127.0.0.1:7709"
    connection._executor = executor

    connection._mark_disconnected(2)

    assert sock.closed is True
    assert connection.connected_host is None
    assert connection._socket is None
    assert connection._executor is None
    assert executor.shutdown_calls == [(False, True)]
