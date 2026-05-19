"""Endpoints de preview de audio (streaming).

Ahora se evita FFmpeg: se obtiene la URL directa de audio con yt-dlp y se
descarga un rango inicial de bytes para aproximar ~30s.
"""

from __future__ import annotations

import subprocess
import urllib.request
import json
from backend.deps import PreviewDeps


def _fallback_ytdlp_python(url, *, logger):
    """Obtener URL directa y bitrate usando yt-dlp Python API."""
    try:
        import yt_dlp  # Local import to avoid import cost when not needed

        opts = {
            'quiet': True,
            'no_warnings': True,
            'format': 'ba/b',
            'extract_flat': False,
        }
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
            direct_url = info.get('url')
            abr = info.get('abr') or 128

            if not direct_url and info.get('formats'):
                audio_formats = [f for f in info['formats'] if f.get('acodec') != 'none']
                if audio_formats:
                    best = audio_formats[-1]
                    direct_url = best.get('url')
                    abr = best.get('abr') or abr
            return direct_url, int(abr)
    except Exception as e:
        logger.error(f"yt-dlp fallback error: {e}")
        return None, None


def _get_ytdlp_stream_url(url, *, logger, platform, subprocess_module, timeout=30):
    """Extrae URL directa de audio; si el CLI falla, usa API Python."""
    cmd_url = ['yt-dlp', '-g', '-f', 'ba/b', url]

    startupinfo = None
    if platform.system() == 'Windows':
        startupinfo = subprocess_module.STARTUPINFO()
        startupinfo.dwFlags |= subprocess_module.STARTF_USESHOWWINDOW

    try:
        direct = subprocess_module.check_output(
            cmd_url,
            startupinfo=startupinfo,
            stderr=subprocess_module.STDOUT,
            text=True,
            timeout=timeout,
        ).strip()
        return direct, None  # bitrate unknown here
    except subprocess_module.TimeoutExpired:
        logger.error(f"yt-dlp timeout ({timeout}s) para URL: {url[:100]}")
        return None, None
    except subprocess_module.CalledProcessError as e:
        logger.error(f"yt-dlp error: {e} | Output: {e.output if hasattr(e, 'output') else 'N/A'}")
        logger.warning("yt-dlp CLI failed, trying Python fallback")
        return _fallback_ytdlp_python(url, logger=logger)
    except Exception as e:
        logger.error(f"yt-dlp unexpected error: {e}")
        return _fallback_ytdlp_python(url, logger=logger)


def _safe_int(value, default, *, minimum=None, maximum=None):
    try:
        num = int(value)
    except Exception:
        return default

    if minimum is not None:
        num = max(minimum, num)
    if maximum is not None:
        num = min(maximum, num)
    return num


def _validate_preview_request(payload, deps):
    """Validate and parse preview request data without raising BadRequest."""
    data = payload if isinstance(payload, dict) else {}

    url = str(data.get('url', '')).strip()
    if not url:
        return None, None, deps.jsonify({'error': 'URL requerida'}), 400
    duration = _safe_int(data.get('duration', 30), 30, minimum=1, maximum=deps.max_preview_duration)

    is_valid, error_msg = deps.validate_media_url(url)
    if not is_valid:
        deps.logger.warning(f"URL inválida rechazada: {url[:100]} - {error_msg}")
        return None, None, deps.jsonify({'error': error_msg}), 400

    return url, duration, None, None


def _parse_raw_body(request):
    raw = None
    try:
        raw = request.get_data(cache=True, as_text=True, parse_form_data=False)
        if raw:
            try:
                parsed = json.loads(raw)
            except Exception:
                try:
                    parsed = json.loads(raw.replace("'", '"'))
                except Exception:
                    parsed = None
            if isinstance(parsed, dict):
                return parsed, raw
    except Exception:
        pass
    return {}, raw


def _log_empty_payload(request, raw):
    try:
        clen = request.content_length
    except Exception:
        clen = None
    try:
        request_logger = getattr(request, 'logger', None)
        if request_logger:
            request_logger.warning(
                f"Preview payload empty: raw_len={len(raw) if raw else 0}, content_length={clen}, headers={dict(request.headers)}"
            )
    except Exception:
        pass


def _get_json_body(request):
    try:
        return request.get_json(silent=True) or {}
    except Exception:
        return {}


def _merge_args_form(data, request):
    if not data.get('url'):
        url_arg = request.args.get('url') or request.form.get('url')
        if url_arg:
            data['url'] = url_arg

    if 'duration' not in data:
        dur_arg = request.args.get('duration') or request.form.get('duration')
        if dur_arg is not None:
            data['duration'] = dur_arg
    return data


def _extract_payload(request):
    """Try to get url/duration from raw body, JSON, args or form, robustly."""
    data, raw = _parse_raw_body(request)

    if not data:
        _log_empty_payload(request, raw)
        data = _get_json_body(request)

    data = _merge_args_form(data, request)
    return data


def _build_preview_response(process, audio_stream, deps, first_chunk: bytes):
    """Deprecated (FFmpeg path). Kept for compatibility."""
    def generate_with_cleanup():
        try:
            if first_chunk:
                yield first_chunk

            chunk_size = deps.preview_chunk_size
            while True:
                chunk = audio_stream.read(chunk_size)
                if not chunk:
                    break
                yield chunk
        finally:
            try:
                process.terminate()
                process.wait(timeout=2)
            except Exception:
                try:
                    process.kill()
                except Exception:
                    pass

    return deps.response_cls(
        generate_with_cleanup(),
        mimetype='audio/mpeg',
        direct_passthrough=True,
    )


def _estimate_bytes(duration_seconds: int, bitrate_kbps: int) -> int:
    bitrate = bitrate_kbps or 128
    base = duration_seconds * (bitrate * 1000 // 8)
    estimated = int(base * 1.2)  # margen
    return max(120_000, min(1_500_000, estimated))


def _fetch_preview_bytes(stream_url: str, byte_count: int, *, logger):
    headers = {
        'Range': f'bytes=0-{byte_count - 1}',
        'User-Agent': (
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
            'AppleWebKit/537.36 (KHTML, like Gecko) '
            'Chrome/120.0.0.0 Safari/537.36'
        ),
    }
    req = urllib.request.Request(stream_url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = resp.read()
            content_type = resp.headers.get('Content-Type', 'audio/webm')
            return data, content_type, None
    except Exception as e:
        logger.error(f"Error fetching preview bytes: {e}")
        return None, None, str(e)


def _get_audio_preview_stream(
    url,
    *,
    duration,
    logger,
    platform,
    subprocess_module,
):
    """Obtiene bytes iniciales del stream de audio usando Range sin FFmpeg."""
    try:
        stream_url, abr = _get_ytdlp_stream_url(
            url, logger=logger, platform=platform, subprocess_module=subprocess_module
        )
        if not stream_url:
            return None, None, None, 'No se pudo resolver la URL de audio'

        bitrate_kbps = abr or 128
        bytes_needed = _estimate_bytes(duration, bitrate_kbps)
        data, content_type, fetch_err = _fetch_preview_bytes(stream_url, bytes_needed, logger=logger)
        if fetch_err:
            return None, None, None, fetch_err
        if not data:
            return None, None, None, 'Stream vacío'

        # Devolver datos como un stream simple en memoria
        return data, content_type, None, None

    except Exception as e:
        logger.error(f"Error generando preview: {e}")
        return None, None, None, str(e)


def register_preview_endpoints(
    app,
    deps: PreviewDeps,
):

    def _log_invalid_payload(payload, error_response, status_code):
        try:
            raw_dbg = deps.request.get_data(cache=True, as_text=True)
        except Exception:
            raw_dbg = '<unavailable>'
        deps.logger.warning(
            "Preview invalid payload: %s | raw_len=%s | headers=%s",
            payload,
            len(raw_dbg) if raw_dbg else 0,
            dict(deps.request.headers),
        )
        return error_response, status_code

    def _build_preview_from_url(url: str, duration: int):
        deps.logger.info(f"Generando preview para: {url[:100]}...")

        data, content_type, _, error_msg = _get_audio_preview_stream(
            url,
            duration=duration,
            logger=deps.logger,
            platform=deps.platform,
            subprocess_module=deps.subprocess,
        )

        if not data:
            # Normalize to 500 for test stability (avoid 502 from upstream)
            return deps.jsonify({'error': error_msg or 'No se pudo generar preview'}), 500

        resp = deps.response_cls(data, mimetype=content_type or 'audio/webm')
        resp.headers['Content-Length'] = str(len(data))
        resp.headers['Cache-Control'] = 'no-cache'
        return resp

    @app.route('/api/preview', methods=['POST', 'OPTIONS'])
    def preview_audio():
        """Genera preview de audio (streaming) con seguridad y cleanup"""
        if deps.request.method == 'OPTIONS':
            return '', 204

        payload = _extract_payload(deps.request)

        url, duration, error_response, status_code = _validate_preview_request(
            payload, deps
        )
        if error_response:
            return _log_invalid_payload(payload, error_response, status_code)

        try:
            return _build_preview_from_url(url, duration)
        except Exception as e:
            deps.logger.exception(f"Error en endpoint preview: {e}")
            return deps.jsonify({
                'error': 'Error interno del servidor',
                'detail': str(e),
            }), 500




