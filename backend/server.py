from flask import Flask, request, jsonify, send_file, send_from_directory, Response
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_compress import Compress
from flask_caching import Cache
import yt_dlp
import os
import subprocess
import threading
from pathlib import Path
import uuid
import logging
import re
from queue import Queue, Empty
import time
import json
import sched
from flask_socketio import SocketIO, emit, join_room
import weakref
import atexit
import platform
from urllib.parse import urlparse

# Route registration helpers (modularization)
from backend.routes_static import register_static_routes
from backend.websocket_handlers import register_websocket_handlers
from backend.api_files import register_file_endpoints
from backend.api_info import register_info_endpoints, get_writable_cookiefile
from backend.api_preview import register_preview_endpoints
from backend.api_downloads import register_download_endpoints
from backend.api_health_search import register_health_search_endpoints

from backend.deps import DownloadsDeps, FilesDeps, HealthSearchDeps, InfoDeps, PreviewDeps

# Security utilities (extracted for modularity)
from backend.security_utils import (
    sanitize_filename as _sanitize_filename,
    sanitize_input as _sanitize_input,
    validate_media_url as _validate_media_url,
    validate_youtube_url as _validate_youtube_url,
)

# Importar configuración desde el paquete backend
from backend import config

# Configuración de limpieza desde config.py
CLEANUP_INTERVAL = config.CLEANUP_DELAY
FILE_MAX_AGE = config.FILE_MAX_AGE if hasattr(config, 'FILE_MAX_AGE') else 1800

# ========== CONSTANTS ==========
MAX_PREVIEW_DURATION = 60  # seconds
MAX_FILENAME_LENGTH = 200
PREVIEW_CHUNK_SIZE = 262144  # 256KB for better streaming performance
DEFAULT_CHUNK_SIZE = 8192
MSG_FINALIZING = 'Finalizando...'

app = Flask(__name__)
# SECURITY: Use environment variable for SECRET_KEY in production
# Stable fallback prevents session invalidation on restart and multi-worker mismatch
_default_secret = 'pullsound-dev-key-change-in-production'  # NOSONAR
app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY', _default_secret)

# Initialize Flask extensions
Compress(app)  # Gzip compression for responses
cache = Cache(app, config={'CACHE_TYPE': config.CACHE_TYPE, 'CACHE_DEFAULT_TIMEOUT': config.CACHE_DEFAULT_TIMEOUT})
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["1000 per hour"],  # FIX: Aumentado de 100 a 1000 para archivos estáticos
    storage_uri="memory://"
)

# SECURITY FIX #6: Restrict CORS to localhost only
if config.ALLOWED_ORIGINS == "*":
    _socketio_origins = "*"
else:
    _socketio_origins = list(config.ALLOWED_ORIGINS) + ["file://"]
socketio = SocketIO(
    app,
    cors_allowed_origins=_socketio_origins,
    async_mode='threading'  # threading is more compatible with FFmpeg subprocess on Windows
)

# CORS configurado correctamente - Restringido a localhost
CORS(
    app,
    resources={
        r"/*": {
            "origins": config.ALLOWED_ORIGINS,
            "methods": ["GET", "POST", "DELETE", "OPTIONS"],
            "allow_headers": ["Content-Type"],
        }
    },
)

# ========== STRUCTURED LOGGING ==========
class JSONFormatter(logging.Formatter):
    """Format logs as JSON for better parsing and monitoring"""
    def format(self, record):
        log_data = {
            'timestamp': self.formatTime(record),
            'level': record.levelname,
            'message': record.getMessage(),
            'module': record.module,
        }
        if hasattr(record, 'task_id'):
            log_data['task_id'] = record.task_id
        if hasattr(record, 'user_ip'):
            log_data['user_ip'] = record.user_ip
        return json.dumps(log_data)

# Configure logging
handler = logging.StreamHandler()
if config.DEBUG_MODE:
    handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
else:
    handler.setFormatter(JSONFormatter())

logging.basicConfig(level=logging.INFO, handlers=[handler])
logger = logging.getLogger(__name__)

# Carpetas desde config (o defaults)
DOWNLOAD_FOLDER = Path(config.DOWNLOADS_DIR)
FRONTEND_FOLDER = Path(config.FRONTEND_DIR)

# Asegurar existencia
DOWNLOAD_FOLDER.mkdir(exist_ok=True, parents=True) # parents=True por si acaso

# Cola de descargas
download_queue = Queue()
active_downloads = {}
downloads_lock = threading.Lock()

# Register static routes and websocket handlers (kept identical behavior)
register_static_routes(app, frontend_folder=FRONTEND_FOLDER, logger=logger)
register_websocket_handlers(
    socketio,
    join_room=join_room,
    emit=emit,
    downloads_lock=downloads_lock,
    active_downloads=active_downloads,
    logger=logger,
)

# Background services (workers + cleanup) must NOT start on import.
# They are started explicitly by main.py or when running this module directly.
workers = []
NUM_WORKERS = 0
cleanup_thread = None
_background_started = False

# IMPROVED: Cancel events for efficient event-based cancellation
cancel_events = {}  # task_id -> threading.Event
cancel_events_lock = threading.Lock()

# FIX #2: Shutdown management
shutdown_event = threading.Event()

# Configuración
MAX_CONCURRENT_DOWNLOADS = config.MAX_CONCURRENT_DOWNLOADS if hasattr(config, 'MAX_CONCURRENT_DOWNLOADS') else 5
CHUNK_SIZE = DEFAULT_CHUNK_SIZE  # Use constant defined above

# ========== PREVIEW PROCESS MANAGEMENT ==========
# Global registry for cleanup of preview processes
_active_preview_processes = weakref.WeakValueDictionary()
_process_lock = threading.Lock()

def validate_media_url(url):
    """Compat wrapper: valida URL con SSRF protection."""
    return _validate_media_url(url, ALLOWED_DOMAINS)

# Removed duplicate functions - using unified versions below (lines 275+)


# ========== GLOBAL CLEANUP HANDLER ==========
def _running_under_pytest() -> bool:
    # Señales comunes de pytest (colección/ejecución).
    # - PYTEST_CURRENT_TEST suele existir durante ejecución, pero no siempre en import-time.
    # - 'pytest' en sys.modules funciona incluso durante colección.
    import sys

    return bool(os.environ.get("PYTEST_CURRENT_TEST")) or ("pytest" in sys.modules)


def cleanup_all_preview_processes():
    """Cleanup global: Mata todos los procesos preview al cerrar servidor"""
    logger.info("Shutting down: cleaning up all preview processes...")
    with _process_lock:
        for process in _active_preview_processes.values():
            try:
                process.terminate()
                process.wait(timeout=2)
            except Exception:
                try:
                    process.kill()
                except Exception:
                    pass
    logger.info("All preview processes cleaned up")




def cleanup_partial_files(title_pattern):
    """Limpia archivos parciales de una descarga cancelada"""
    try:
        partial_extensions = ['.part', '.ytdl', '.temp', '.webp', '.mp4.part']
        count = 0
        for f in DOWNLOAD_FOLDER.glob('*'):
            if title_pattern.lower() in f.name.lower():
                if any(f.name.endswith(ext) for ext in partial_extensions) or f.suffix == '.webp':
                    try:
                        safe_operation(f.unlink)
                        count += 1
                        logger.info(f"Archivo parcial eliminado: {f.name}")
                    except Exception as e:
                        logger.warning(f"No se pudo eliminar {f.name}: {e}")
        return count
    except Exception as e:
        logger.exception("Error limpiando archivos parciales")
        return 0

# ========== THREAD DE LIMPIEZA ==========
def safe_operation(func, *args, retries=5, delay=0.5, **kwargs):
    """Ejecuta una operación con reintentos (para evitar bloqueos de Windows)"""
    for i in range(retries):
        try:
            return func(*args, **kwargs)
        except PermissionError:
            if i == retries - 1:
                raise
            time.sleep(delay * (i + 1))  # Backoff exponencial 0.5, 1.0, 1.5...
        except Exception as e:
            logger.debug(f"Non-permission error in safe_operation: {e}")
            raise

# ========== FUNCIONES DE SEGURIDAD ==========
def validate_filename(filename):
    """
    Sanitiza nombres de archivo para prevenir path traversal
    
    Args:
        filename: Nombre de archivo a sanitizar
        
    Returns:
        Nombre de archivo seguro
    """
    if not filename:
        return "file"
    
    # Remover path separators y caracteres peligrosos
    safe = filename.replace('..', '')
    safe = safe.replace('/', '_')
    safe = safe.replace('\\', '_')
    safe = safe.replace(':', '_')
    safe = safe.replace('*', '_')
    safe = safe.replace('?', '_')
    safe = safe.replace('"', '_')
    safe = safe.replace('<', '_')
    safe = safe.replace('>', '_')
    safe = safe.replace('|', '_')
    
    # Remover espacios iniciales/finales
    safe = safe.strip()
    
    # Si queda vacío después de sanitizar
    if not safe or safe == '_':
        return "file"
    
    return safe

ALLOWED_DOMAINS = [
    'youtube.com',
    'youtu.be',
    'm.youtube.com',
    'music.youtube.com',
    'www.youtube.com',
    'soundcloud.com',
    'www.soundcloud.com',
    'm.soundcloud.com',
    'open.spotify.com',
    'spotify.com',
]

def validate_url(url):
    """
    Valida que la URL esté en la whitelist de dominios permitidos
    
    Args:
        url: URL a validar
        
    Returns:
        True si la URL es válida, False otherwise
    """
    if not url:
        return False
    
    try:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        
        # Verificar que el dominio esté en la whitelist (exact or subdomain match)
        return any(domain == allowed or domain.endswith(f'.{allowed}') for allowed in ALLOWED_DOMAINS)
    except Exception:
        return False

def _is_file_active_download(filename: str) -> bool:
    """Check if a file is currently being downloaded."""
    with downloads_lock:
        return any(
            task.get('filename') == filename
            for task in active_downloads.values()
        )


def _delete_old_file(file_path) -> bool:
    """Try to delete an old file and return success status."""
    try:
        if _is_file_active_download(file_path.name):
            return False
        safe_operation(file_path.unlink)
        logger.info(f"Archivo antiguo eliminado: {file_path.name}")
        return True
    except Exception:
        logger.exception("Error eliminando %s", file_path.name)
        return False


def cleanup_files():
    """Elimina archivos antiguos de la carpeta de descargas"""
    while True:
        try:
            time.sleep(CLEANUP_INTERVAL)
            logger.info("Ejecutando limpieza automática...")
            
            now = time.time()
            count = 0
            
            for file_path in DOWNLOAD_FOLDER.glob('*'):
                if file_path.is_file() and (now - file_path.stat().st_mtime) > FILE_MAX_AGE:
                    if _delete_old_file(file_path):
                        count += 1
            
            if count > 0:
                logger.info(f"Limpieza completada: {count} archivos eliminados")
                
        except Exception:
            logger.exception("Error en thread de limpieza")

def start_background_services():
    """Start worker pool and cleanup thread (idempotent).

    Important: This function is intentionally NOT called at import time to keep
    tests deterministic and prevent background threads from writing logs after
    pytest captures are closed.
    """
    global _background_started, NUM_WORKERS, workers, cleanup_thread
    if _background_started:
        return

    _background_started = True

    # Start cleanup thread
    if cleanup_thread is None or not cleanup_thread.is_alive():
        cleanup_thread = threading.Thread(target=cleanup_files, daemon=True, name="cleanup_thread")
        cleanup_thread.start()

    # Start download worker threads
    NUM_WORKERS = MAX_CONCURRENT_DOWNLOADS
    if NUM_WORKERS < 1:
        NUM_WORKERS = 1

    for _ in range(NUM_WORKERS):
        t = threading.Thread(target=download_worker, daemon=True)
        t.start()
        workers.append(t)

    logger.info(f"✓ {NUM_WORKERS} workers iniciados")



# ========== SECURITY FUNCTIONS ==========

def validate_youtube_url(url):
    """Validates and sanitizes YouTube URLs with SSRF protection"""
    return _validate_youtube_url(
        url,
        max_url_length=config.MAX_URL_LENGTH,
        allowed_domains=ALLOWED_DOMAINS,
        logger=logger,
    )

def sanitize_input(value, max_length=255):
    """Sanitize user input to prevent injection attacks"""
    return _sanitize_input(value, max_length=max_length)

# ========== FUNCIONES AUXILIARES ==========

def sanitize_filename(filename):
    """Limpia el nombre del archivo y valida contra path traversal"""
    return _sanitize_filename(
        filename,
        download_folder=DOWNLOAD_FOLDER,
        max_length=MAX_FILENAME_LENGTH,
        logger=logger,
    )

def generate_chunks(file_path, chunk_size=CHUNK_SIZE):
    """Generador de chunks para streaming."""
    with open(file_path, 'rb') as f:
        try:
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                yield chunk
        except GeneratorExit:
            # Cliente cerró la conexión; salimos sin error
            logger.debug(f"Stream cancelado por el cliente: {file_path}")
            return

def update_task_progress(task_id, status, progress, message):
    """Actualiza el progreso de una tarea"""
    try:
        data = {
            'task_id': task_id,  # CRITICAL FIX: Frontend needs this to route updates
            'status': status,
            'progress': progress,
            'message': message,
            'timestamp': time.time()
        }
        
        with downloads_lock:
            if task_id in active_downloads:
                active_downloads[task_id].update(data)
        
        # Emitir evento SocketIO
        socketio.emit('status_update', data, room=task_id)
        
        logger.info(f"[{task_id}] {progress}% - {message}")
    except Exception:
        logger.exception("Error actualizando progreso")

class DownloadTask:
    """Clase para manejar tareas de descarga"""
    
    def __init__(self, task_id, url, audio_format, quality):
        self.task_id = task_id
        self.url = url
        self.audio_format = audio_format
        self.quality = quality
        self.status = 'queued'
        self.progress = 0
        self.message = 'En cola'
        self.error = None
        self.filename = None
        self.title = None
        self.created_at = time.time()

def check_cancellation(task_id):
    """Verifica si una tarea fue cancelada usando Event (eficiente, sin polling)"""
    with cancel_events_lock:
        if task_id in cancel_events and cancel_events[task_id].is_set():
            return True
    return False


def _build_download_message(downloaded, total, speed) -> str:
    """Build formatted download progress message."""
    downloaded_mb = downloaded / (1024 * 1024)
    total_mb = total / (1024 * 1024) if total > 0 else 0
    speed_mb = speed / (1024 * 1024) if speed else 0
    
    if total > 0:
        message = f"Descargando: {downloaded_mb:.1f}MB / {total_mb:.1f}MB"
    else:
        message = f"Descargando: {downloaded_mb:.1f}MB"
    
    if speed_mb > 0:
        message += f" ({speed_mb:.1f}MB/s)"
    return message


def _calculate_mapped_progress(downloaded: int, total: int) -> float:
    """Calculate mapped download progress (10-90%)."""
    if total <= 0:
        return 10.0
    percentage = (downloaded / total) * 100
    mapped = 10 + ((percentage / 100) * 80)
    return round(max(10, min(90, mapped)), 2)


def progress_hook(d, task_id):
    """Hook para yt-dlp que reporta progreso - IMPROVED with Event-based cancellation"""
    # IMPROVED: Use threading.Event instead of polling dictionary
    if check_cancellation(task_id):
        raise yt_dlp.utils.DownloadError('Download cancelled by user')

    status = d.get('status')
    
    if status == 'downloading':
        downloaded = d.get('downloaded_bytes', 0)
        total = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
        speed = d.get('speed', 0)
        
        mapped_progress = _calculate_mapped_progress(downloaded, total)
        message = _build_download_message(downloaded, total, speed)
        update_task_progress(task_id, 'downloading', mapped_progress, message)
    
    elif status == 'finished':
        update_task_progress(task_id, 'converting', 90.0, 'Descarga compl. - Procesando...')

def _handle_postprocessor_started(task_id: str, pp: str) -> None:
    """Handle postprocessor started status."""
    handlers = {
        'FFmpegExtractAudio': (92, 'Extrayendo audio...'),
        'EmbedThumbnail': (95, 'Incrustando portada...'),
        'FFmpegMetadata': (97, 'Añadiendo info...'),
    }
    progress, message = handlers.get(pp, (None, None))
    if progress is not None:
        update_task_progress(task_id, 'converting', progress, message)


def _handle_postprocessor_finished(task_id: str, pp: str) -> None:
    """Handle postprocessor finished status."""
    handlers = {
        'FFmpegExtractAudio': (94, 'Audio listo'),
        'EmbedThumbnail': (96, 'Portada lista'),
        'FFmpegMetadata': (99, MSG_FINALIZING),
    }
    progress, message = handlers.get(pp, (None, None))
    if progress is not None:
        update_task_progress(task_id, 'converting', progress, message)


def _get_source_bitrate(video_info: dict) -> int:
    """Extract source bitrate from video info."""
    source_bitrate = video_info.get('abr', 160)
    if not source_bitrate or source_bitrate == 0:
        formats = video_info.get('formats', [])
        audio_formats = [f for f in formats if f.get('vcodec') == 'none' and f.get('abr')]
        source_bitrate = max(f.get('abr', 160) for f in audio_formats) if audio_formats else 160
    return int(source_bitrate)


def _get_adjusted_quality(task_id: str, quality_int: int, video_info: dict) -> int:
    """Calculate adjusted quality based on mode and source bitrate."""
    requested_quality = int(quality_int)
    
    if quality_int >= config.HIGH_QUALITY_THRESHOLD:
        logger.info(f"[{task_id}] Modo alta calidad: Usando calidad solicitada {requested_quality}kbps")
        return requested_quality
    
    # OPTIMIZED MODE: Check source bitrate to avoid upsampling
    source_bitrate = _get_source_bitrate(video_info)
    logger.info(f"[{task_id}] Calidad de audio fuente: {source_bitrate}kbps")
    
    if requested_quality > source_bitrate:
        logger.warning(
            f"[{task_id}] Calidad solicitada ({requested_quality}kbps) excede "
            f"fuente ({source_bitrate}kbps). Ajustando a {source_bitrate}kbps"
        )
        return source_bitrate
    
    return requested_quality


def postprocessor_hook(d, task_id):
    """Hook para yt-dlp que reporta progreso de post-procesamiento"""
    # Check cancellation during post-processing
    # Note: Using DownloadError as PostProcessingError doesn't exist in yt-dlp
    if check_cancellation(task_id):
        raise yt_dlp.utils.DownloadError('Post-processing cancelled by user')
    
    status = d.get('status')
    pp = d.get('postprocessor')
    
    if status == 'started':
        _handle_postprocessor_started(task_id, pp)
    elif status == 'finished':
        # Check cancellation after each PP step
        if check_cancellation(task_id):
            raise yt_dlp.utils.DownloadError('Post-processing cancelled by user')
        _handle_postprocessor_finished(task_id, pp)

def _get_video_info(task_id: str, url: str) -> tuple:
    """Extract video information and return title, duration, and clean title."""
    update_task_progress(task_id, 'fetching_info', 5, 'Obteniendo información del video...')
    
    info_opts = {
        'quiet': True,
        'no_warnings': True,
        'nocheckcertificate': True,
        'source_address': '0.0.0.0',
        'http_headers': {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'},
        'extractor_args': {'youtube': {'player_client': ['android', 'web']}},
        'noplaylist': True,
    }

    # Optional: inject cookiefile from env to bypass YouTube bot checks when deployed
    cookiefile = get_writable_cookiefile()
    if cookiefile:
        info_opts['cookiefile'] = cookiefile
    
    with yt_dlp.YoutubeDL(info_opts) as ydl:
        video_info = ydl.extract_info(url, download=False)
        video_title = video_info.get('title', 'video_sin_titulo')
        duration = video_info.get('duration', 0)
    
    clean_title = sanitize_filename(video_title)
    return video_info, video_title, duration, clean_title


def _configure_ydl_options(task_id: str, clean_title: str, task, adjusted_quality: int) -> dict:
    """Configure yt-dlp options based on task parameters."""
    output_filename = f"{clean_title}.%(ext)s"
    output_template = str(DOWNLOAD_FOLDER / output_filename)
    
    requested_quality_int = int(task.quality)
    
    if requested_quality_int >= config.HIGH_QUALITY_THRESHOLD:
        logger.info(f"[{task_id}] Modo ALTA CALIDAD ({requested_quality_int}kbps): Descargando video completo")
        base_opts = config.YT_DLP_OPTIONS_HIGH_QUALITY
    else:
        logger.info(f"[{task_id}] Modo OPTIMIZADO ({requested_quality_int}kbps): Descargando solo audio")
        base_opts = config.YT_DLP_OPTIONS_OPTIMIZED
    
    ydl_opts = {
        **base_opts,
        'outtmpl': output_template,
        'progress_hooks': [lambda d: progress_hook(d, task_id)],
        'postprocessor_hooks': [lambda d: postprocessor_hook(d, task_id)],
    }

    # Optional: reuse cookiefile for actual download if provided
    cookiefile = get_writable_cookiefile()
    if cookiefile:
        ydl_opts['cookiefile'] = cookiefile
    
    return _set_format_postprocessors(ydl_opts, task.audio_format, adjusted_quality)


def _set_format_postprocessors(ydl_opts: dict, audio_format: str, adjusted_quality: int) -> dict:
    """Add format-specific postprocessors to yt-dlp options."""
    postprocessor_map = {
        'mp3': [
            {'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': str(adjusted_quality)},
            {'key': 'FFmpegMetadata', 'add_metadata': True},
            {'key': 'EmbedThumbnail'},
        ],
        'flac': [
            {'key': 'FFmpegExtractAudio', 'preferredcodec': 'flac'},
            {'key': 'FFmpegMetadata', 'add_metadata': True},
            {'key': 'EmbedThumbnail'},
        ],
        'wav': [
            {'key': 'FFmpegExtractAudio', 'preferredcodec': 'wav'},
            {'key': 'FFmpegMetadata', 'add_metadata': True},
        ],
        'm4a': [
            {'key': 'FFmpegExtractAudio', 'preferredcodec': 'm4a', 'preferredquality': str(adjusted_quality)},
            {'key': 'FFmpegMetadata', 'add_metadata': True},
            {'key': 'EmbedThumbnail'},
        ],
        'opus': [
            {'key': 'FFmpegExtractAudio', 'preferredcodec': 'opus', 'preferredquality': str(adjusted_quality)},
            {'key': 'FFmpegMetadata', 'add_metadata': True},
            {'key': 'EmbedThumbnail'},
        ],
    }
    
    if audio_format in postprocessor_map:
        ydl_opts['postprocessors'] = postprocessor_map[audio_format]
    
    return ydl_opts


def _perform_download(task_id: str, url: str, ydl_opts: dict) -> None:
    """Execute the actual download using yt-dlp."""
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
    except yt_dlp.utils.DownloadError as e:
        if 'cancelled by user' in str(e).lower():
            logger.info(f"[{task_id}] Descarga cancelada por el usuario")
            update_task_progress(task_id, 'cancelled', 0, 'Cancelado')
            raise
        else:
            raise


def _complete_download(task_id: str, clean_title: str, task, video_title: str, duration: int) -> None:
    """Finalize successful download and update task status."""
    final_filename = f"{clean_title}.{task.audio_format}"
    filepath = DOWNLOAD_FOLDER / final_filename
    
    if not filepath.exists():
        raise FileNotFoundError("El archivo no se creó correctamente")
    
    file_size = filepath.stat().st_size
    file_size_mb = file_size / (1024 * 1024)
    
    update_task_progress(task_id, 'verifying', 95, f'Verificando ({file_size_mb:.1f}MB)...')
    
    task_data = {
        'status': 'completed',
        'progress': 100,
        'message': f'¡Completado! {final_filename}',
        'filename': final_filename,
        'title': video_title,
        'file_size': file_size,
        'duration': duration
    }
    
    with downloads_lock:
        active_downloads[task_id].update(task_data)
        task_copy = active_downloads[task_id].copy()
    
    socketio.emit('status_update', task_copy, room=task_id)
    logger.info(f"[{task_id}] ✓ Completado: {final_filename} ({file_size_mb:.1f}MB)")

    # NOTE: File is NOT auto-deleted here. The frontend triggers cleanup via
    # /api/cleanup/<filename> after the download completes, and the background
    # cleanup thread removes files older than FILE_MAX_AGE as a safety net.

def _process_spotify_download(task):
    """Procesa una descarga de Spotify usando spotdl"""
    import subprocess
    import shutil
    import tempfile
    
    task_id = task.task_id
    url = task.url
    format_ext = task.audio_format.lower()
    if format_ext not in ['mp3', 'flac', 'wav']:
        format_ext = 'mp3'
        
    update_task_progress(task_id, 'starting', 0, 'Iniciando descarga de Spotify...')
    update_task_progress(task_id, 'converting', 40, 'Buscando y descargando con spotdl...')
    
    with tempfile.TemporaryDirectory() as temp_dir:
        output_template = f"{temp_dir}/{{artist}} - {{title}}.{format_ext}"
        
        try:
            cmd = [
                'spotdl', url,
                '--format', format_ext,
                '--output', output_template,
                '--log-level', 'ERROR'
            ]
            
            # Formatos lossy aceptan bitrate numérico
            if format_ext == 'mp3':
                # spotdl espera "320k" o "auto", etc. pero el usuario pasa 320, 256.
                # Si task.quality es un número
                try:
                    bitrate = int(task.quality)
                    cmd.extend(['--bitrate', f"{bitrate}k"])
                except (ValueError, TypeError):
                    pass
            elif format_ext in ['flac', 'wav']:
                cmd.extend(['--bitrate', 'disable'])
                
            subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=300)
            
            update_task_progress(task_id, 'finalizing', 90, MSG_FINALIZING)
            
            files = list(Path(temp_dir).glob(f"*.{format_ext}"))
            if not files:
                raise RuntimeError("spotdl no produjo ningún archivo")
                
            downloaded_file = files[0]
            clean_title = downloaded_file.stem
            
            final_path = DOWNLOAD_FOLDER / downloaded_file.name
            shutil.move(str(downloaded_file), str(final_path))
            
            _complete_download(task_id, clean_title, task, clean_title, duration=0)
            
        except subprocess.CalledProcessError as e:
            logger.exception(f"spotdl failed: {e.stderr}")
            update_task_progress(task_id, 'error', 0, 'Error descargando de Spotify')
        except Exception as e:
            logger.exception("Error inesperado con spotdl")
            update_task_progress(task_id, 'error', 0, f'Error: {str(e)[:100]}')


def process_download(task):
    """Procesa una descarga con reporte de progreso"""
    task_id = task.task_id
    
    try:
        if 'spotify.com' in task.url:
            _process_spotify_download(task)
            return

        # 1. INICIO
        update_task_progress(task_id, 'starting', 0, 'Iniciando proceso...')
        
        # 2. PREPARANDO
        update_task_progress(task_id, 'preparing', 5, 'Preparando descarga...')
        url = task.url
        
        if 'soundcloud.com' in url and 'utm_' in url:
            try:
                from urllib.parse import urlparse, urlunparse, parse_qs, urlencode
                parsed = urlparse(url)
                q = parse_qs(parsed.query)
                q = {k: v for k, v in q.items() if not k.startswith('utm_')}
                url = urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, urlencode(q, doseq=True), parsed.fragment))
            except Exception:
                pass
        
        # 3-4. Obtener información del video
        video_info, video_title, duration, clean_title = _get_video_info(task_id, url)
        update_task_progress(task_id, 'info_ready', 7, f'Video: {video_title[:50]}...')
        
        # 5. CONFIGURANDO
        update_task_progress(task_id, 'configuring', 9, 'Configurando descarga...')
        adjusted_quality = _get_adjusted_quality(task_id, int(task.quality), video_info)
        ydl_opts = _configure_ydl_options(task_id, clean_title, task, adjusted_quality)
        
        # 6. DESCARGANDO
        logger.info(f"[{task_id}] Iniciando descarga: {video_title}")
        update_task_progress(task_id, 'converting', 80, 'Descargando...')
        _perform_download(task_id, url, ydl_opts)
        
        # 7-10. POST-PROCESAMIENTO Y FINALIZACIÓN
        update_task_progress(task_id, 'converting', 85, 'Optimizando audio...')
        update_task_progress(task_id, 'finalizing', 90, MSG_FINALIZING)
        _complete_download(task_id, clean_title, task, video_title, duration)
        
    except yt_dlp.utils.DownloadError as e:
        if 'cancelled by user' in str(e).lower():
            logger.info(f"[{task_id}] Descarga cancelada por el usuario")
        else:
            logger.exception("[%s] ✗ Error de descarga", task_id)
            update_task_progress(task_id, 'error', 0, f'Error: {str(e)[:100]}')
    except Exception as e:
        logger.exception("[%s] ✗ Error inesperado", task_id)
        update_task_progress(task_id, 'error', 0, f'Error: {str(e)[:100]}')


def download_worker():
    """Worker que procesa descargas con shutdown graceful"""
    while not shutdown_event.is_set():
        try:
            # Use timeout to allow checking shutdown_event
            task = download_queue.get(timeout=1)
            if task is None:
                break
            
            try:
                process_download(task)
            except Exception:
                logger.exception("Error en worker")
            finally:
                download_queue.task_done()
                
        except Empty:  # Fixed: catch specific exception
            continue  # Check shutdown_event again

 # Workers are started via start_background_services()

# FIX #2 Part 3: Graceful shutdown handler
def graceful_shutdown():
    """Cierra workers de forma ordenada"""
    if shutdown_event.is_set():
        return  # Already shutting down
    
    logger.info("Iniciando cierre graceful de workers...")
    shutdown_event.set()
    
    # Wait for workers to finish current tasks (if they were started)
    for worker in workers:
        worker.join(timeout=30)
        if worker.is_alive():
            logger.warning(f"Worker {worker.name} no terminó en 30s")
    
    logger.info("✓ Workers cerrados correctamente")

# atexit already imported at module level (line 21)
if not _running_under_pytest():
    atexit.register(graceful_shutdown)
    atexit.register(cleanup_all_preview_processes)


# ========== RUTAS DE LA API ==========

# Extracted endpoints (info/preview/download control)
register_info_endpoints(
    app,
    InfoDeps(
        request=request,
        jsonify=jsonify,
        limiter=limiter,
        cache=cache,
        config=config,
        logger=logger,
        yt_dlp=yt_dlp,
        validate_youtube_url=validate_youtube_url,
        sanitize_input=sanitize_input,
    ),
)

register_preview_endpoints(
    app,
    PreviewDeps(
        request=request,
        jsonify=jsonify,
        response_cls=Response,
        logger=logger,
        validate_media_url=validate_media_url,
        max_preview_duration=MAX_PREVIEW_DURATION,
        preview_chunk_size=PREVIEW_CHUNK_SIZE,
        process_lock=_process_lock,
        active_preview_processes=_active_preview_processes,
        platform=platform,
        subprocess=subprocess,
        threading=threading,
    ),
)

register_download_endpoints(
    app,
    DownloadsDeps(
        request=request,
        jsonify=jsonify,
        limiter=limiter,
        config=config,
        logger=logger,
        uuid=uuid,
        download_task_cls=DownloadTask,
        validate_youtube_url=validate_youtube_url,
        sanitize_input=sanitize_input,
        downloads_lock=downloads_lock,
        active_downloads=active_downloads,
        download_queue=download_queue,
        socketio=socketio,
        cancel_events_lock=cancel_events_lock,
        cancel_events=cancel_events,
        cleanup_partial_files=cleanup_partial_files,
        threading=threading,
        time=time,
    ),
)

# File-related routes (extracted for modularity)
register_file_endpoints(
    app,
    FilesDeps(
        response_cls=Response,
        jsonify=jsonify,
        download_folder=DOWNLOAD_FOLDER,
        generate_chunks=generate_chunks,
        downloads_lock=downloads_lock,
        active_downloads=active_downloads,
        safe_operation=safe_operation,
        logger=logger,
    ),
)


# Enhanced download endpoint with timestamp and metadata support

def check_ffmpeg():
    """Verifica FFmpeg"""
    try:
        import subprocess
        result = subprocess.run(['ffmpeg', '-version'], 
                              capture_output=True, 
                              text=True,
                              timeout=5)
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


# Health + search routes (extracted for modularity)
register_health_search_endpoints(
    app,
    HealthSearchDeps(
        request=request,
        jsonify=jsonify,
        downloads_lock=downloads_lock,
        active_downloads=active_downloads,
        download_queue=download_queue,
        max_concurrent_downloads=MAX_CONCURRENT_DOWNLOADS,
        download_folder=DOWNLOAD_FOLDER,
        frontend_folder=FRONTEND_FOLDER,
        check_ffmpeg=check_ffmpeg,
        limiter=limiter,
        config=config,
        logger=logger,
    ),
)

if __name__ == '__main__':
    # When running directly, start background services.
    start_background_services()

    if not check_ffmpeg():
        logger.warning("FFmpeg no disponible")
    else:
        logger.info("FFmpeg detectado")
    
    if not FRONTEND_FOLDER.exists():
        logger.error(f"Frontend no encontrado: {FRONTEND_FOLDER}")
    else:
        logger.info(f"Frontend: {FRONTEND_FOLDER}")
    
    logger.info("="*60)
    logger.info(f"🚀 Servidor PullSound v{config.PROJECT_INFO['version']}")
    logger.info("="*60)
    logger.info("Frontend: http://localhost:5000")
    logger.info("API: http://localhost:5000/api/")
    logger.info(f"Workers: {NUM_WORKERS}")
    logger.info(f"Rate Limits: {config.RATE_LIMIT_DOWNLOADS} downloads, {config.RATE_LIMIT_INFO} info")
    logger.info("="*60)
    


    socketio.run(app, debug=False, port=config.SERVER_PORT, host=config.SERVER_HOST)