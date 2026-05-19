"""Endpoints de control de descargas: download, status, cancel.

Extraído de server.py para reducir tamaño sin cambiar comportamiento.
"""

from __future__ import annotations

from backend.deps import DownloadsDeps


def _parse_payload(request):
    data = request.get_json(silent=True) or {}
    url = data.get('url')

    raw_format = data.get('format')
    audio_format = raw_format.strip() if isinstance(raw_format, str) else raw_format

    raw_quality = data.get('quality')
    quality = raw_quality.strip() if isinstance(raw_quality, str) else raw_quality

    return url, audio_format, quality


def _validate_required(url, audio_format, quality, jsonify):
    if not url:
        return jsonify({'error': 'URL requerida'}), 400
    if not audio_format:
        return jsonify({'error': 'Formato de audio requerido'}), 400
    if not quality:
        return jsonify({'error': 'Calidad de audio requerida'}), 400
    return None


def _sanitize_inputs(deps, url, audio_format, quality):
    url_s = deps.sanitize_input(url, max_length=2048)
    fmt_s = deps.sanitize_input(audio_format, max_length=10)
    qual_s = deps.sanitize_input(quality, max_length=10)
    return url_s, fmt_s, qual_s


def _validate_format(audio_format, deps):
    if audio_format not in deps.config.AUDIO_FORMATS:
        return deps.jsonify({
            'error': f'Formato inválido. Formatos disponibles: {", ".join(deps.config.AUDIO_FORMATS.keys())}'
        }), 400
    return None


def _validate_quality(quality, deps):
    try:
        quality_int = int(quality)
        valid_qualities = [128, 192, 256, 320]
        if quality_int not in valid_qualities:
            return deps.jsonify({
                'error': (
                    'Calidad inválida. Valores permitidos: '
                    f'{", ".join(map(str, valid_qualities))} kbps'
                )
            }), 400
    except (ValueError, TypeError):
        return deps.jsonify({'error': 'Calidad debe ser un número'}), 400
    return None


def _validate_youtube(url, deps):
    if not deps.validate_youtube_url(url):
        return deps.jsonify({'error': 'URL de YouTube inválida'}), 400
    return None


def _run_validators(validators):
    for check in validators:
        resp = check()
        if resp:
            return resp
    return None


def _handle_download_request(deps, request):
    url, audio_format, quality = _parse_payload(request)

    resp = _run_validators((
        lambda: _validate_required(url, audio_format, quality, deps.jsonify),
        lambda: _validate_youtube(url, deps),
    ))
    if resp:
        return resp

    url, audio_format, quality = _sanitize_inputs(deps, url, audio_format, quality)

    resp = _run_validators((
        lambda: _validate_format(audio_format, deps),
        lambda: _validate_quality(quality, deps),
    ))
    if resp:
        return resp

    return _enqueue_task(deps, url, audio_format, quality)


def _enqueue_task(deps, url, audio_format, quality):
    deps.logger.info(
        f"Nueva solicitud de descarga: {url[:50]}... - {audio_format} - {quality}kbps"
    )

    task_id = str(deps.uuid.uuid4())
    task = deps.download_task_cls(task_id, url, audio_format, quality)

    with deps.downloads_lock:
        deps.active_downloads[task_id] = task.__dict__

    deps.download_queue.put(task)

    deps.logger.info(f"[{task_id}] Tarea encolada. Cola: {deps.download_queue.qsize()}")

    return deps.jsonify({
        'success': True,
        'task_id': task_id,
        'status': 'queued',
        'queue_position': deps.download_queue.qsize(),
    })


def _set_cancel_event(deps, task_id):
    with deps.cancel_events_lock:
        if task_id not in deps.cancel_events:
            deps.cancel_events[task_id] = deps.threading.Event()
        deps.cancel_events[task_id].set()


def _mark_task_cancelled(deps, task_id):
    with deps.downloads_lock:
        task = deps.active_downloads.get(task_id)
        if not task:
            return None, None
        title = task.get('title', '')
        task['status'] = 'cancelled'
        task['message'] = 'Cancelando...'
        return task, title


def _emit_cancel_status(deps, task_id, task):
    deps.socketio.emit('status_update', task, room=task_id)


def _schedule_partial_cleanup(deps, title, task_id):
    if not title:
        return

    def delayed_cleanup():
        deps.time.sleep(2)
        count = deps.cleanup_partial_files(title)
        if count > 0:
            deps.logger.info(f"[{task_id}] Limpiados {count} archivos parciales")

    cleanup_thread = deps.threading.Thread(target=delayed_cleanup, daemon=True)
    cleanup_thread.start()


def register_download_endpoints(
    app,
    deps: DownloadsDeps,
):
    @app.route('/api/cancel/<task_id>', methods=['POST', 'OPTIONS'])
    def cancel_task(task_id):
        """Cancela una tarea en curso - IMPROVED with Event-based cancellation"""
        if deps.request.method == 'OPTIONS':
            return '', 204

        _set_cancel_event(deps, task_id)

        task, title = _mark_task_cancelled(deps, task_id)
        if not task:
            return deps.jsonify({'error': 'Tarea no encontrada'}), 404

        _emit_cancel_status(deps, task_id, task)
        _schedule_partial_cleanup(deps, title, task_id)

        return deps.jsonify({'status': 'cancelled'}), 200

    @app.route('/api/download', methods=['POST', 'OPTIONS'])
    @deps.limiter.limit(deps.config.RATE_LIMIT_DOWNLOADS)
    def download_audio():
        """Encola una descarga"""
        if deps.request.method == 'OPTIONS':
            return '', 204

        try:
            return _handle_download_request(deps, deps.request)

        except Exception as e:
            deps.logger.error(f"Error encolando descarga: {str(e)}")
            # SECURITY: Don't expose stack traces in production
            return deps.jsonify({'error': 'Error interno del servidor'}), 500

    @app.route('/api/status/<task_id>', methods=['GET', 'OPTIONS'])
    def get_download_status(task_id):
        """Obtiene el estado de una descarga"""
        if deps.request.method == 'OPTIONS':
            return '', 204

        try:
            with deps.downloads_lock:
                if task_id in deps.active_downloads:
                    return deps.jsonify(deps.active_downloads[task_id])
                else:
                    return deps.jsonify({'error': 'Tarea no encontrada'}), 404
        except Exception as e:
            deps.logger.error(f"Error obteniendo estado: {str(e)}")
            return deps.jsonify({'error': str(e)}), 500
