"""Endpoints de información de video.

Extraído de server.py para reducir tamaño sin cambiar comportamiento.
"""

from __future__ import annotations

import os

from backend.deps import InfoDeps


MAX_PLAYLIST_PAGE_SIZE = 50
DEFAULT_PLAYLIST_PAGE_SIZE = 10


def _info_cache_key(req):
    """Cache key that varies by URL + pagination to avoid stale pages."""

    try:
        data = req.get_json(silent=True) or {}
    except Exception:
        data = {}

    url = req.args.get('url') or data.get('url') or ''
    offset = req.args.get('offset', data.get('offset', 0))
    limit = req.args.get('limit', data.get('limit', DEFAULT_PLAYLIST_PAGE_SIZE))

    return f"info:{url}:{offset}:{limit}"


def _to_int(value, default, *, minimum=None, maximum=None):
    try:
        num = int(value)
    except Exception:
        return default

    if minimum is not None:
        num = max(minimum, num)
    if maximum is not None:
        num = min(maximum, num)
    return num


def _parse_request(request):
    data = request.get_json(silent=True) or {}
    url = request.args.get('url') or data.get('url')

    offset = _to_int(
        request.args.get('offset', data.get('offset', 0)),
        default=0,
        minimum=0,
    )
    limit = _to_int(
        request.args.get('limit', data.get('limit', DEFAULT_PLAYLIST_PAGE_SIZE)),
        default=DEFAULT_PLAYLIST_PAGE_SIZE,
        minimum=1,
        maximum=MAX_PLAYLIST_PAGE_SIZE,
    )

    return url, offset, limit


def _build_ydl_opts(offset: int, limit: int):
    return {
        'quiet': True,
        'no_warnings': True,
        'nocheckcertificate': True,
        'source_address': '0.0.0.0',
        'http_headers': {
            'User-Agent': (
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                'AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/120.0.0.0 Safari/537.36'
            )
        },
        'extractor_args': {'youtube': {'player_client': ['android', 'web']}},
        'extract_flat': 'in_playlist',
        'playliststart': offset + 1,
        'playlistend': offset + limit,
    }


def _add_cookiefile(ydl_opts: dict) -> dict:
    """Inject cookiefile into yt-dlp opts if env var is present and readable."""
    cookiefile = os.getenv('YTDLP_COOKIES_FILE')
    if cookiefile and os.path.exists(cookiefile):
        ydl_opts['cookiefile'] = cookiefile
    return ydl_opts


def _normalize_playlist(info, offset: int, limit: int):
    entries = [entry for entry in info.get('entries', []) if entry]
    raw_total = info.get('playlist_count') or info.get('n_entries')
    processed = offset + len(entries)

    if raw_total is None:
        has_more = len(entries) >= limit
        total = processed + (1 if has_more else 0)
    else:
        total = raw_total
        has_more = processed < total

    next_offset = processed if has_more else None

    return {
        'is_playlist': True,
        'title': info.get('title'),
        'count': total,
        'offset': offset,
        'limit': limit,
        'has_more': has_more,
        'next_offset': next_offset,
        'entries': [
            {
                'url': entry.get('url'),
                'title': entry.get('title'),
                'thumbnail': (
                    entry.get('thumbnails', [{}])[-1].get('url')
                    if entry.get('thumbnails')
                    else None
                ),
                'duration': entry.get('duration'),
            }
            for entry in entries
        ],
        'thumbnail': info.get('thumbnail'),
    }


def _normalize_single(info):
    return {
        'is_playlist': False,
        'title': info.get('title'),
        'duration': info.get('duration'),
        'thumbnail': info.get('thumbnail'),
        'uploader': info.get('uploader'),
        'view_count': info.get('view_count'),
    }


def register_info_endpoints(
    app,
    deps: InfoDeps,
):
    @app.route('/api/info', methods=['POST', 'OPTIONS'])
    @deps.limiter.limit(deps.config.RATE_LIMIT_INFO)
    @deps.cache.cached(timeout=90, key_prefix=lambda: _info_cache_key(deps.request))
    def get_video_info():
        """Obtiene información del video"""
        if deps.request.method == 'OPTIONS':
            return '', 204

        try:
            url, offset, limit = _parse_request(deps.request)

            if not url:
                return deps.jsonify({'error': 'URL requerida'}), 400

            # Validate URL
            if not deps.validate_youtube_url(url):
                return deps.jsonify({'error': 'URL de YouTube inválida'}), 400

            url = deps.sanitize_input(url, max_length=2048)

            deps.logger.info(f"Obteniendo info de: {url[:100]}...")

            ydl_opts = _add_cookiefile(_build_ydl_opts(offset, limit))

            with deps.yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)

                # Detectar si es playlist
                if info.get('_type') == 'playlist':
                    return deps.jsonify(_normalize_playlist(info, offset, limit))

                return deps.jsonify(_normalize_single(info))

        except Exception as e:
            deps.logger.error(f"Error obteniendo info: {str(e)}")
            return deps.jsonify({'error': str(e)}), 500
