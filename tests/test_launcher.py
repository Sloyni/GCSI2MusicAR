import socket
import app as launcher


def test_existing_musicar_is_reused_without_bind(monkeypatch):
    monkeypatch.setattr(launcher,"probe_service",lambda port:True)
    listener,url=launcher.prepare_service(8765)
    assert listener is None and url=="http://127.0.0.1:8765"


def test_foreign_busy_port_gets_a_reserved_free_port(monkeypatch):
    monkeypatch.setattr(launcher,"probe_service",lambda port:False)
    with socket.socket() as occupied:
        occupied.bind(("127.0.0.1",0));occupied.listen()
        port=occupied.getsockname()[1]
        listener,url=launcher.prepare_service(port)
        try:
            assert listener.getsockname()[1]!=port
            assert url.endswith(str(listener.getsockname()[1]))
        finally:listener.close()


def test_free_port_is_reserved_before_server_start(monkeypatch):
    monkeypatch.setattr(launcher,"probe_service",lambda port:False)
    listener,url=launcher.prepare_service(0)
    try:assert url==f"http://127.0.0.1:{listener.getsockname()[1]}"
    finally:listener.close()
