def test_create_app_can_start_background_services(monkeypatch):
    from application import create_app

    # No iniciar threads reales durante test
    import server as backend_server

    called = {"n": 0}

    def fake_start():
        called["n"] += 1

    monkeypatch.setattr(backend_server, "start_background_services", fake_start)

    app, socketio = create_app(testing=True, start_background_services=True)
    assert app is backend_server.app
    assert socketio is backend_server.socketio
    assert called["n"] == 1
