"""Exercise the real add-in socket boundary without importing Fusion's runtime."""

import importlib.util
import json
import logging
import socket
import sys
import threading
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock

import pytest


@pytest.fixture
def socket_module(monkeypatch):
    package = ModuleType("_socket_policy_addon")
    package.__path__ = []
    package.get_logger = logging.getLogger
    monkeypatch.setitem(sys.modules, package.__name__, package)
    path = Path(__file__).resolve().parents[1] / "addon/server/socket_server.py"
    spec = importlib.util.spec_from_file_location(
        f"{package.__name__}.socket_server", path
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(
    "host", ["0.0.0.0", "192.0.2.1", "example.com", "host.docker.internal", "::1"]
)
def test_remote_constructor_rejected(socket_module, monkeypatch, host):
    factory = Mock()
    monkeypatch.setattr(socket_module.socket, "socket", factory)
    with pytest.raises(ValueError, match="Remote connections are disabled"):
        socket_module.Fusion360MCPServer(Mock(), host=host)
    factory.assert_not_called()


def test_local_binding_is_numeric(socket_module, monkeypatch):
    server = socket_module.Fusion360MCPServer(Mock(), host="localhost", port=12345)
    listener = Mock()
    monkeypatch.setattr(socket_module.socket, "socket", Mock(return_value=listener))
    assert server._bind_socket()
    listener.bind.assert_called_once_with(("127.0.0.1", 12345))
    listener.listen.assert_called_once()
    server._close_socket()


@pytest.mark.parametrize("operation", ["start", "bind", "restart"])
def test_changed_host_cannot_bind_or_retry(socket_module, monkeypatch, operation):
    server = socket_module.Fusion360MCPServer(Mock())
    server.host = "0.0.0.0"
    factory = Mock()
    delay = Mock()
    monkeypatch.setattr(socket_module.socket, "socket", factory)
    monkeypatch.setattr(socket_module.time, "sleep", delay)
    if operation == "restart":
        server._running = True
        server._accept_loop_with_restart()
        assert not server.is_running()
    else:
        with pytest.raises(ValueError, match="Remote connections are disabled"):
            server.start() if operation == "start" else server._bind_socket()
    factory.assert_not_called()
    delay.assert_not_called()


def test_nonlocal_peer_closed_before_thread_or_dispatch(socket_module, monkeypatch):
    bridge = Mock()
    server = socket_module.Fusion360MCPServer(bridge)
    server._running = True
    client = Mock()

    def accept():
        server._running = False
        return client, ("192.0.2.1", 12345)

    server._socket = Mock()
    server._socket.accept.side_effect = accept
    worker = Mock()
    monkeypatch.setattr(socket_module.threading, "Thread", worker)
    server._accept_loop()
    client.close.assert_called_once()
    worker.assert_not_called()
    bridge.submit.assert_not_called()


def test_local_json_roundtrip(socket_module):
    bridge = Mock()
    bridge.submit.return_value = {"status": "success", "result": {"pong": True}}
    server = socket_module.Fusion360MCPServer(bridge, port=0)
    assert server._bind_socket()
    port = server._socket.getsockname()[1]
    try:
        server._running = True
        server._accept_thread = threading.Thread(
            target=server._accept_loop, daemon=True
        )
        server._accept_thread.start()
        with socket.create_connection(("127.0.0.1", port), timeout=3) as client:
            client.sendall(b'{"type":"ping"}\n')
            result = json.loads(client.recv(4096))
        assert result["result"]["pong"] is True
        bridge.submit.assert_called_once_with({"type": "ping"})
    finally:
        server.stop()