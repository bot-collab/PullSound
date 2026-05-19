"""
Unit tests for config.py
"""
import pytest
from pathlib import Path


class TestConfig:
    """Tests de configuración del proyecto"""
    
    def test_import_config(self):
        """Verifica que config se puede importar"""
        import config
        assert config is not None
    
    def test_audio_formats_structure(self):
        """Verifica estructura de formatos de audio"""
        from config import AUDIO_FORMATS
        
        assert 'mp3' in AUDIO_FORMATS
        assert 'flac' in AUDIO_FORMATS
        assert 'wav' in AUDIO_FORMATS
        assert 'm4a' in AUDIO_FORMATS
        assert 'opus' in AUDIO_FORMATS
        
        # Verificar estructura
        assert 'codec' in AUDIO_FORMATS['mp3']
        assert 'qualities' in AUDIO_FORMATS['mp3']
        assert len(AUDIO_FORMATS['mp3']['qualities']) == 4
    
    def test_quality_threshold(self):
        """Verifica threshold de calidad"""
        from config import HIGH_QUALITY_THRESHOLD
        
        assert HIGH_QUALITY_THRESHOLD == 256
        assert isinstance(HIGH_QUALITY_THRESHOLD, int)
    
    def test_ytdlp_options_base(self):
        """Verifica opciones base de yt-dlp"""
        from config import YT_DLP_OPTIONS_BASE
        
        assert 'quiet' in YT_DLP_OPTIONS_BASE
        assert 'retries' in YT_DLP_OPTIONS_BASE
        assert YT_DLP_OPTIONS_BASE['retries'] >= 5
        assert 'writethumbnail' in YT_DLP_OPTIONS_BASE
    
    def test_directories_structure(self):
        """Verifica que directorios necesarios existen"""
        from config import DOWNLOADS_DIR, BASE_DIR
        
        assert BASE_DIR.exists()
        assert BASE_DIR.is_dir()
        
        # DOWNLOADS_DIR se crea si no existe
        if not DOWNLOADS_DIR.exists():
            DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)
        
        assert DOWNLOADS_DIR.exists()
    
    def test_rate_limits(self):
        """Verifica rate limits configurados"""
        from config import RATE_LIMIT_DOWNLOADS, RATE_LIMIT_INFO
        
        assert RATE_LIMIT_DOWNLOADS is not None
        assert RATE_LIMIT_INFO is not None
        assert 'per' in RATE_LIMIT_DOWNLOADS
        assert 'per' in RATE_LIMIT_INFO
    
    def test_project_info(self):
        """Verifica información del proyecto"""
        from config import PROJECT_INFO
        
        assert 'name' in PROJECT_INFO
        assert 'version' in PROJECT_INFO
        assert 'author' in PROJECT_INFO
        assert PROJECT_INFO['name'] == 'PullSound'
        assert PROJECT_INFO['author'] == '3sc0b0t'
