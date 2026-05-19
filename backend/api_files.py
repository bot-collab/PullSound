"""Endpoints relacionados a archivos descargados.

Extraído de server.py para reducir tamaño y acoplamiento.
Mantiene exactamente las mismas rutas y respuestas.
"""

from __future__ import annotations

import tempfile
import zipfile
from pathlib import Path

from backend.deps import FilesDeps


ACCESS_DENIED_MSG = 'Acceso denegado'


def _validate_no_path_traversal(*, filepath, base_folder, filename, logger, jsonify_fn, context: str):
    """Valida que filepath esté dentro de base_folder.

    Mantiene compatibilidad con Python 3.7+.
    """

    try:
        # Python 3.9+
        if not filepath.is_relative_to(base_folder.resolve()):
            logger.warning(f"Path traversal attempt{context}: {filename}")
            return jsonify_fn({'error': ACCESS_DENIED_MSG}), 403
    except AttributeError:
        # Python 3.7-3.8 fallback
        try:
            filepath.resolve().relative_to(base_folder.resolve())
        except ValueError:
            logger.warning(f"Path traversal attempt{context}: {filename}")
            return jsonify_fn({'error': ACCESS_DENIED_MSG}), 403

    return None


def _resolve_and_validate_path(*, deps: FilesDeps, filename: str, context: str):
    """Resolve path and run traversal guard."""

    filepath = (deps.download_folder / filename).resolve()
    deps.logger.debug(f"Resolved path{context}: {filepath}")

    denial = _validate_no_path_traversal(
        filepath=filepath,
        base_folder=deps.download_folder,
        filename=filename,
        logger=deps.logger,
        jsonify_fn=deps.jsonify,
        context=context,
    )

    return filepath, denial


def _is_active_download(deps: FilesDeps, filename: str) -> bool:
    with deps.downloads_lock:
        return any(
            task.get('filename') == filename
            for task in deps.active_downloads.values()
        )


def _already_deleted_response(deps: FilesDeps, filename: str):
    deps.logger.info(f"Archivo ya no existe (ya eliminado): {filename}")
    return deps.jsonify({'success': True, 'message': 'File already deleted'}), 200


def _delete_file(deps: FilesDeps, filepath, filename: str):
    try:
        if _is_active_download(deps, filename):
            deps.logger.warning(
                f"Cannot delete {filename} - file is being used by active download"
            )
            return deps.jsonify({'error': 'File is currently being downloaded', 'success': False}), 409

        deps.safe_operation(filepath.unlink)
        deps.logger.info(f"✓ Archivo eliminado exitosamente: {filename}")
        return deps.jsonify({'success': True, 'message': 'File deleted'}), 200

    except PermissionError as e:
        deps.logger.error(f"PermissionError deleting {filename}: {e}")
        return deps.jsonify({
            'error': 'File is locked by another process',
            'success': False,
            'details': str(e)
        }), 409
    except Exception as e:
        deps.logger.error(f"Error deleting {filename}: {type(e).__name__}: {e}")
        return deps.jsonify({
            'error': 'Failed to delete file',
            'success': False,
            'details': str(e)
        }), 500


def _parse_zip_payload(request, jsonify_fn):
    payload = request.get_json(silent=True) or {}
    filenames = payload.get('filenames') if isinstance(payload, dict) else None

    if not isinstance(filenames, list) or not filenames:
        return None, (jsonify_fn({'error': 'Lista de archivos requerida'}), 400)

    cleaned = [name for name in filenames if isinstance(name, str) and name.strip()]
    if not cleaned:
        return None, (jsonify_fn({'error': 'Lista de archivos requerida'}), 400)

    return cleaned, None


def _collect_zip_candidates(deps: FilesDeps, filenames):
    valid_files = []
    missing_files = []

    for name in filenames:
        filepath, denial = _resolve_and_validate_path(
            deps=deps,
            filename=name,
            context=' in zip',
        )
        if denial is not None:
            return None, None, denial

        if not filepath.exists():
            missing_files.append(name)
            continue

        valid_files.append((name, filepath))

    return valid_files, missing_files, None


def _validate_zip_candidates(valid_files, missing_files, jsonify_fn):
    if valid_files:
        return None

    msg = 'No se encontraron archivos para comprimir'
    if missing_files:
        sample = ', '.join(missing_files[:3])
        msg = f'{msg}: {sample}'
    return jsonify_fn({'error': msg}), 400


def _create_zip_file(valid_files, deps: FilesDeps):
    tmp_file = tempfile.NamedTemporaryFile(
        delete=False,
        suffix='.zip',
        dir=deps.download_folder
    )

    with zipfile.ZipFile(tmp_file, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as zipf:
        for original_name, file_path in valid_files:
            zipf.write(file_path, arcname=Path(original_name).name)

    tmp_path = Path(tmp_file.name)
    tmp_file.close()
    return tmp_path


def _build_zip_response(deps: FilesDeps, tmp_path: Path):
    response = deps.response_cls(
        deps.generate_chunks(tmp_path),
        mimetype='application/zip',
        direct_passthrough=True
    )
    response.headers['Content-Disposition'] = 'attachment; filename="playlist.zip"'
    response.headers['Content-Length'] = str(tmp_path.stat().st_size)
    response.headers['Cache-Control'] = 'no-cache'

    response.call_on_close(lambda: deps.safe_operation(tmp_path.unlink))
    return response


def _create_and_stream_zip(deps: FilesDeps, valid_files):
    tmp_path = None
    try:
        tmp_path = _create_zip_file(valid_files, deps)
        return _build_zip_response(deps, tmp_path)
    except Exception as e:
        deps.logger.error(f"Error creando zip de playlist: {type(e).__name__}: {e}")
        try:
            if tmp_path and tmp_path.exists():
                deps.safe_operation(tmp_path.unlink)
        except Exception:
            pass
        return deps.jsonify({'error': 'No se pudo crear el archivo zip'}), 500


def _handle_zip_playlist_request(deps: FilesDeps, request):
    filenames, payload_error = _parse_zip_payload(request, deps.jsonify)
    if payload_error:
        return payload_error

    valid_files, missing_files, denial = _collect_zip_candidates(deps, filenames)
    if denial is not None:
        return denial

    validation_error = _validate_zip_candidates(valid_files, missing_files, deps.jsonify)
    if validation_error:
        return validation_error

    return _create_and_stream_zip(deps, valid_files)


def register_file_endpoints(app, deps: FilesDeps):
    """Registra endpoints de archivos y cleanup."""

    @app.route('/api/file/<path:filename>', methods=['GET'])
    def get_file(filename):
        """Envía el archivo"""
        try:
            filepath = (deps.download_folder / filename).resolve()

            denial = _validate_no_path_traversal(
                filepath=filepath,
                base_folder=deps.download_folder,
                filename=filename,
                logger=deps.logger,
                jsonify_fn=deps.jsonify,
                context='',
            )
            if denial is not None:
                return denial

            if not filepath.exists():
                deps.logger.error(f"Archivo no encontrado: {filepath}")
                return deps.jsonify({'error': 'Archivo no encontrado'}), 404

            file_size = filepath.stat().st_size

            response = deps.response_cls(
                deps.generate_chunks(filepath),
                mimetype='application/octet-stream',
                direct_passthrough=True
            )

            response.headers['Content-Disposition'] = f'attachment; filename="{filename}"'
            response.headers['Content-Length'] = str(file_size)
            response.headers['Accept-Ranges'] = 'bytes'
            response.headers['Cache-Control'] = 'no-cache'

            deps.logger.info(f"Enviando: {filename} ({file_size} bytes)")

            return response

        except Exception as e:
            deps.logger.error(f"Error enviando archivo: {str(e)}")
            return deps.jsonify({'error': str(e)}), 500

    @app.route('/api/cleanup/<path:filename>', methods=['DELETE', 'OPTIONS'])
    def cleanup_file(filename):
        """Elimina archivo temporal (idempotent)"""
        from flask import request

        if request.method == 'OPTIONS':
            return '', 204

        try:
            # Detailed logging for debugging
            deps.logger.info(f"Cleanup request for: {filename}")

            filepath, denial = _resolve_and_validate_path(
                deps=deps,
                filename=filename,
                context=' in cleanup',
            )
            if denial is not None:
                return denial

            if not filepath.exists():
                return _already_deleted_response(deps, filename)

            return _delete_file(deps, filepath, filename)

        except Exception as e:
            deps.logger.error(f"Unexpected error in cleanup for {filename}: {type(e).__name__}: {e}")
            return deps.jsonify({
                'error': 'Internal server error',
                'success': False,
                'details': str(e)
            }), 500

    @app.route('/api/playlist/zip', methods=['POST'])
    def zip_playlist():
        """Comprime múltiples archivos descargados en un ZIP temporal."""
        from flask import request
        return _handle_zip_playlist_request(deps, request)
