def test_websocket_join_emits_existing_status(monkeypatch):
    from flask import Flask
    from flask_socketio import SocketIO

    from websocket_handlers import register_websocket_handlers

    app = Flask(__name__)
    socketio = SocketIO(app, async_mode="threading")

    active_downloads = {"room-1": {"task_id": "room-1", "status": "queued"}}

    class DummyLogger:
        def info(self, *_a, **_k):
            # Stub logger to silence real logging in tests.
            return None

    import threading
    lock = threading.Lock()

    register_websocket_handlers(
        socketio,
        join_room=__import__("flask_socketio").join_room,
        emit=__import__("flask_socketio").emit,
        downloads_lock=lock,
        active_downloads=active_downloads,
        logger=DummyLogger(),
    )

    client = socketio.test_client(app, flask_test_client=app.test_client())
    assert client.is_connected()

    client.emit("join", {"task_id": "room-1"})
    received = client.get_received()

    # Debe haber al menos un emit de status_update
    assert any(m.get("name") == "status_update" for m in received)
