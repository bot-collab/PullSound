from pathlib import Path


def test_static_routes_fallbacks_when_files_missing(tmp_path):
    from flask import Flask
    from routes_static import register_static_routes

    app = Flask(__name__)

    class DummyLogger:
        def error(self, *_a, **_k):
            pass

    # Frontend folder vacío -> dispara fallbacks
    register_static_routes(app, frontend_folder=tmp_path, logger=DummyLogger())

    client = app.test_client()

    r1 = client.get("/")
    assert r1.status_code == 404

    r2 = client.get("/robots.txt")
    assert r2.status_code == 200
    assert b"Disallow" in r2.data

    r3 = client.get("/sitemap.xml")
    assert r3.status_code == 200
    assert b"urlset" in r3.data

    r4 = client.get("/does-not-exist.css")
    assert r4.status_code == 404
