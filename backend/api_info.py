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


def _handle_spotify_track_info(url, deps):
    import requests
    import re
    deps.logger.info(f"Usando Spotify oEmbed + HTML Parsing (Vista Rápida) para: {url[:100]}...")
    try:
        resp_html = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=5)
        thumbnail = None
        track_title = 'Spotify Track'
        img_matches = re.findall(r'https://i\.scdn\.co/image/[a-zA-Z0-9]+', resp_html.text)
        if img_matches:
            thumbnail = img_matches[0]
        else:
            resp_oembed = requests.get(f"https://open.spotify.com/oembed?url={url}", timeout=5)
            if resp_oembed.status_code == 200:
                data = resp_oembed.json()
                thumbnail = data.get('thumbnail_url')
                track_title = data.get('title', track_title)
        artist = 'Spotify'
        title_match = re.search(r'<title>(.*?)</title>', resp_html.text)
        if title_match:
            title_text = title_match.group(1).replace(' | Spotify', '')
            if ' - song and lyrics by ' in title_text:
                track_title, artist = title_text.split(' - song and lyrics by ', 1)
            elif ' - song by ' in title_text:
                track_title, artist = title_text.split(' - song by ', 1)
        return deps.jsonify({
            'is_playlist': False,
            'title': f"{artist} - {track_title}",
            'duration': 0,
            'thumbnail': thumbnail,
            'uploader': artist,
            'view_count': None,
        })
    except Exception as e:
        deps.logger.warning(f"Error en vista rápida Spotify: {e}. Cayendo a spotdl...")
        return None

def _handle_spotify_playlist_info(url, offset, limit, deps):
    import subprocess
    import json
    import tempfile
    import os
    deps.logger.info(f"Usando spotdl para extraer tracks: {url[:100]}...")
    with tempfile.NamedTemporaryFile(suffix='.spotdl', delete=False) as tf:
        temp_path = tf.name
    try:
        subprocess.run(['spotdl', 'save', url, '--save-file', temp_path], capture_output=True, text=True, check=True)
        with open(temp_path, 'r', encoding='utf-8') as f:
            spotdl_data = json.load(f)
        if not spotdl_data:
            raise ValueError("No se encontraron datos")
        if len(spotdl_data) > 1 or 'playlist' in url or 'album' in url:
            entries = [{'url': t.get('url'), 'title': f"{t.get('artist', '')} - {t.get('name', '')}".strip(" -"), 'thumbnail': t.get('cover_url'), 'duration': t.get('duration')} for t in spotdl_data]
            paginated_entries = entries[offset:offset + limit]
            total = len(entries)
            has_more = offset + len(paginated_entries) < total
            next_offset = offset + len(paginated_entries) if has_more else None
            return deps.jsonify({
                'is_playlist': True,
                'title': spotdl_data[0].get('list_name') or spotdl_data[0].get('album_name') or 'Spotify Playlist',
                'count': total,
                'offset': offset,
                'limit': limit,
                'has_more': has_more,
                'next_offset': next_offset,
                'entries': paginated_entries,
                'thumbnail': spotdl_data[0].get('cover_url'),
            })
        else:
            track = spotdl_data[0]
            return deps.jsonify({
                'is_playlist': False,
                'title': f"{track.get('artist', '')} - {track.get('name', '')}".strip(" -"),
                'duration': track.get('duration'),
                'thumbnail': track.get('cover_url'),
                'uploader': track.get('artist'),
                'view_count': None,
            })
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)

def _handle_spotify_info(url, offset, limit, deps):
    if '/track/' in url:
        res = _handle_spotify_track_info(url, deps)
        if res:
            return res
    return _handle_spotify_playlist_info(url, offset, limit, deps)

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

            # Interceptar Spotify y usar oEmbed para tracks (Híbrido) o spotdl para playlists
            if 'spotify.com' in url:
                return _handle_spotify_info(url, offset, limit, deps)

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
