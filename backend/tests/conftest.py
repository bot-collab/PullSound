"""
Test configuration and shared fixtures
"""
import pytest
import sys
from pathlib import Path

# Add backend to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from application import create_app
app, socketio = create_app(testing=True)
from config import DOWNLOADS_DIR
import os
import server


@pytest.fixture
def client():
    """Flask test client"""
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    with app.test_client() as client:
        yield client


@pytest.fixture(autouse=True)
def isolate_download_queue(monkeypatch):
    """Stub the download queue to avoid real background work during tests."""
    tasks = []

    def fake_put(task):
        tasks.append(task)

    def fake_qsize():
        return len(tasks)

    monkeypatch.setattr(server.download_queue, 'put', fake_put)
    monkeypatch.setattr(server.download_queue, 'qsize', fake_qsize)

    # Keep active_downloads clean between tests
    yield
    with server.downloads_lock:
        server.active_downloads.clear()
    tasks.clear()


@pytest.fixture
def socket_client():
    """SocketIO test client"""
    return socketio.test_client(app, flask_test_client=app.test_client())


@pytest.fixture
def cleanup_downloads():
    """Limpia archivos de prueba después de cada test"""
    yield
    # Cleanup after test
    if DOWNLOADS_DIR.exists():
        for file in DOWNLOADS_DIR.glob('test_*'):
            try:
                file.unlink()
            except Exception:
                pass


@pytest.fixture
def mock_youtube_url():
    """URL de prueba de YouTube"""
    return "https://www.youtube.com/watch?v=dQw4w9WgXcQ"


@pytest.fixture
def mock_playlist_url():
    """URL de prueba de playlist"""
    return "https://www.youtube.com/playlist?list=PLrAXtmErZgOeiKm4sgNOknGvNjby9efdf"


@pytest.fixture
def sample_video_data():
    """Datos de ejemplo de un video"""
    return {
        'title': 'Test Video',
        'duration': 180,
        'thumbnail': 'https://i.ytimg.com/vi/test/maxresdefault.jpg',
        'uploader': 'Test Channel',
        'view_count': 1000000
    }
