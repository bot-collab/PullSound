"""Tests adicionales para mejorar cobertura de server.py sin cambiar comportamiento.

Cubren helpers que no dependen de yt-dlp/FFmpeg reales.
"""

import os
from pathlib import Path

import pytest


def test_validate_filename_sanitizes_dangerous_chars():
    import server

    assert server.validate_filename("../evil") != "../evil"
    assert ".." not in server.validate_filename("..")
    assert "/" not in server.validate_filename("a/b")
    assert "\\" not in server.validate_filename("a\\b")


def test_validate_url_whitelist_basic():
    import server

    assert server.validate_url("https://www.youtube.com/watch?v=x") is True
    assert server.validate_url("https://soundcloud.com/track") is True
    assert server.validate_url("https://example.com") is False
    assert server.validate_url("") is False


def test_safe_operation_retries_on_permission_error(monkeypatch):
    import server

    calls = {"n": 0}

    def flaky():
        calls["n"] += 1
        if calls["n"] < 3:
            raise PermissionError("locked")
        return "ok"

    result = server.safe_operation(flaky, retries=5, delay=0)
    assert result == "ok"
    assert calls["n"] == 3


def test_cleanup_partial_files_deletes_matching_partials(tmp_path, monkeypatch):
    import server

    # Redirect DOWNLOAD_FOLDER to temp
    monkeypatch.setattr(server, "DOWNLOAD_FOLDER", tmp_path)

    # Create files
    (tmp_path / "My Song.part").write_text("x")
    (tmp_path / "My Song.ytdl").write_text("x")
    (tmp_path / "My Song.webp").write_text("x")
    (tmp_path / "Other.txt").write_text("x")

    deleted = server.cleanup_partial_files("My Song")
    assert deleted >= 3
    assert not (tmp_path / "My Song.part").exists()
    assert not (tmp_path / "My Song.ytdl").exists()
    assert not (tmp_path / "My Song.webp").exists()
    assert (tmp_path / "Other.txt").exists()


def test_cleanup_all_preview_processes_calls_terminate(monkeypatch):
    import server

    # Avoid real logging noise
    class DummyLogger:
        def info(self, *_a, **_k):
            # Stub logger for tests; silence real logging.
            return None

    monkeypatch.setattr(server, "logger", DummyLogger())

    class DummyProc:
        def __init__(self):
            self.terminated = False
            self.killed = False

        def terminate(self):
            self.terminated = True

        def wait(self, timeout=None):
            return 0

        def kill(self):
            self.killed = True

    p = DummyProc()

    with server._process_lock:
        # WeakValueDictionary needs a referenced object to keep it alive
        server._active_preview_processes["p"] = p

    server.cleanup_all_preview_processes()
    assert p.terminated is True


def test_start_background_services_idempotent(monkeypatch):
    import server

    # Evitar loops reales
    monkeypatch.setattr(server, "MAX_CONCURRENT_DOWNLOADS", 1)

    def noop_cleanup():
        return

    def noop_worker():
        return

    monkeypatch.setattr(server, "cleanup_files", noop_cleanup)
    monkeypatch.setattr(server, "download_worker", noop_worker)

    # Reset estado
    server._background_started = False
    server.workers.clear()
    server.cleanup_thread = None

    server.start_background_services()
    first_workers = len(server.workers)
    assert first_workers == 1

    server.start_background_services()
    # No duplica
    assert len(server.workers) == first_workers


def test_graceful_shutdown_works_without_started_workers(monkeypatch):
    import server

    class DummyLogger:
        def info(self, *_a, **_k):
            # Stub logger for tests; silence real logging.
            return None

        def warning(self, *_a, **_k):
            # Stub logger for tests; silence real logging.
            return None

    monkeypatch.setattr(server, "logger", DummyLogger())

    server.workers.clear()
    server.shutdown_event.clear()
    server.graceful_shutdown()
    assert server.shutdown_event.is_set() is True
