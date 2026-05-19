"""Contenedores de dependencias para registrar endpoints.

Objetivo: reducir el número de parámetros en funciones `register_*` sin cambiar
comportamiento (solo re-empacar dependencias).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class InfoDeps:
    request: Any
    jsonify: Callable
    limiter: Any
    cache: Any
    config: Any
    logger: Any
    yt_dlp: Any
    validate_youtube_url: Callable[[str], bool]
    sanitize_input: Callable[..., str]


@dataclass(frozen=True)
class PreviewDeps:
    request: Any
    jsonify: Callable
    response_cls: Any
    logger: Any
    validate_media_url: Callable[[str], tuple[bool, str]]
    max_preview_duration: int
    preview_chunk_size: int
    process_lock: Any
    active_preview_processes: dict
    platform: Any
    subprocess: Any
    threading: Any


@dataclass(frozen=True)
class DownloadsDeps:
    request: Any
    jsonify: Callable
    limiter: Any
    config: Any
    logger: Any
    uuid: Any
    download_task_cls: Any
    validate_youtube_url: Callable[[str], bool]
    sanitize_input: Callable[..., str]
    downloads_lock: Any
    active_downloads: dict
    download_queue: Any
    socketio: Any
    cancel_events_lock: Any
    cancel_events: dict
    cleanup_partial_files: Callable[[str], int]
    threading: Any
    time: Any


@dataclass(frozen=True)
class FilesDeps:
    response_cls: Any
    jsonify: Callable
    download_folder: Any
    generate_chunks: Callable
    downloads_lock: Any
    active_downloads: dict
    safe_operation: Callable
    logger: Any


@dataclass(frozen=True)
class HealthSearchDeps:
    request: Any
    jsonify: Callable
    downloads_lock: Any
    active_downloads: dict
    download_queue: Any
    max_concurrent_downloads: int
    download_folder: Any
    frontend_folder: Any
    check_ffmpeg: Callable[[], bool]
    limiter: Any
    config: Any
    logger: Any
