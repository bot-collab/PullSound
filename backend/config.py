"""
Configuración del proyecto YouTube Audio Converter
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Cargar variables de entorno desde .env
load_dotenv()

# Directorios base
# Ajustado para estar en backend/config.py
BASE_DIR = Path(__file__).parent.parent 
BACKEND_DIR = BASE_DIR / 'backend'
FRONTEND_DIR = BASE_DIR / 'frontend'
DOWNLOADS_DIR = BACKEND_DIR / 'downloads'

# Configuración del servidor
SERVER_HOST = os.getenv('SERVER_HOST', '0.0.0.0')

_raw_port = os.getenv('SERVER_PORT') or os.getenv('PORT')
_clean_port = str(_raw_port or '').strip()
if _clean_port.startswith('$') or not _clean_port:
    SERVER_PORT = 5000
else:
    try:
        SERVER_PORT = int(_clean_port)
    except (ValueError, TypeError):
        SERVER_PORT = 5000

DEBUG_MODE = os.getenv('DEBUG_MODE', 'False').lower() == 'true'

# Rate Limiting
RATE_LIMIT_DOWNLOADS = os.getenv('RATE_LIMIT_DOWNLOADS', '10 per minute')
RATE_LIMIT_INFO = os.getenv('RATE_LIMIT_INFO', '30 per minute')
MAX_URL_LENGTH = 2048

# Caching
CACHE_TYPE = 'simple'
CACHE_DEFAULT_TIMEOUT = 300

# Configuración de audio
AUDIO_FORMATS = {
    'mp3': {
        'codec': 'mp3',
        'qualities': ['128', '192', '256', '320']  # Restored 320 for maximum quality
    },
    'flac': {
        'codec': 'flac',
        'qualities': ['16bit_44kHz', '24bit_96kHz', '24bit_192kHz']
    },
    'wav': {
        'codec': 'wav',
        'qualities': ['16bit_44kHz', '24bit_96kHz', '32bit_192kHz'] 
    },
    'm4a': {
        'codec': 'm4a',
        'qualities': ['128', '192', '256', '320']  # Restored 320
    },
    'opus': {
        'codec': 'opus',
        'qualities': ['128', '192', '256', '320']  # Restored 320
    }
}

# DUAL-MODE DOWNLOAD STRATEGY
# Quality threshold: >= this value uses full video download
HIGH_QUALITY_THRESHOLD = 256

# Configuración de yt-dlp
# DUAL MODE: High quality = full video, Medium/Low = audio-only
YT_DLP_OPTIONS_BASE = {
    'quiet': False,
    'no_warnings': False,
    'nocheckcertificate': True,
    'no_check_certificates': True,
    'prefer_insecure': True,
    'geo_bypass': True,
    'source_address': '0.0.0.0',
    'http_headers': {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    },
    'extractor_args': {
        'youtube': {
            'player_client': ['android', 'web']
        }
    },
    'noplaylist': True,
    'http_chunk_size': 1048576,  # 1 MB
    'buffersize': 1024,  # 1 KB
    'retries': 10,
    'fragment_retries': 10,
    'writethumbnail': True,
}

# HIGH QUALITY mode: Download full video (256/320 kbps)
YT_DLP_OPTIONS_HIGH_QUALITY = {
    **YT_DLP_OPTIONS_BASE,
    'format': 'bestvideo+bestaudio/best',  # Full video + audio for maximum quality
    'keepvideo': True,  # Keep video temporarily for audio extraction
}

# OPTIMIZED mode: Download audio-only (128/192 kbps)
YT_DLP_OPTIONS_OPTIMIZED = {
    **YT_DLP_OPTIONS_BASE,
    'format': 'bestaudio/best',  # Audio-only for speed
    'keepvideo': False,
}

# Default (for backward compatibility)
YT_DLP_OPTIONS = YT_DLP_OPTIONS_OPTIMIZED

# Tiempo de limpieza y otros
CLEANUP_DELAY = int(os.getenv('CLEANUP_DELAY', 300))  # 5 minutos
FILE_MAX_AGE = int(os.getenv('FILE_MAX_AGE', 1800))  # 30 minutos
MAX_CONCURRENT_DOWNLOADS = int(os.getenv('MAX_CONCURRENT_DOWNLOADS', 5))


def _parse_origins(raw: str):
    if raw == "*":
        return "*"
    return [origin.strip() for origin in raw.split(',') if origin and origin.strip()]


# Lista de orígenes permitidos para CORS/SocketIO, configurable por entorno
ALLOWED_ORIGINS = _parse_origins(
    os.getenv(
        'ALLOWED_ORIGINS',
        '*' if DEBUG_MODE else 'http://localhost:5000,http://127.0.0.1:5000'
    )
)


# YouTube API (for search feature)
YOUTUBE_API_KEY = os.getenv('YOUTUBE_API_KEY', None)

# Redis (optional, for advanced queue management)
REDIS_URL = os.getenv('REDIS_URL', None)
ENABLE_REDIS = os.getenv('ENABLE_REDIS', 'false').lower() == 'true'

# Metrics (optional)
ENABLE_METRICS = os.getenv('ENABLE_METRICS', 'true').lower() == 'true'

# Información del proyecto
PROJECT_INFO = {
    'name': 'PullSound',
    'version': '3.0.0',
    'author': '3sc0b0t',
    'date': '2025-12-26',
    'description': 'Convertidor de múltiples plataformas formatos de audio'
}