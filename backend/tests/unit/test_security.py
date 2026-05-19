"""
Tests unitarios para funciones de seguridad
"""
import pytest
from pathlib import Path


class TestSecurity:
    """Tests de seguridad y validación"""
    
    def test_path_traversal_prevention(self):
        """Test prevención de path traversal"""
        from server import validate_filename
        
        dangerous_names = [
            '../etc/passwd',
            '..\\..\\windows\\system32',
            '/etc/passwd',
            'C:\\Windows\\System32\\config\\sam'
        ]
        
        for name in dangerous_names:
            safe = validate_filename(name)
            assert '..' not in safe
            assert '/' not in safe
            assert '\\' not in safe
    
    def test_url_whitelist(self):
        """Test whitelist de URLs permitidas"""
        # Import the whitelist if it exists
        try:
            from server import ALLOWED_DOMAINS
            
            # YouTube domains should be allowed
            youtube_domains = [
                'youtube.com',
                'youtu.be',
                'm.youtube.com'
            ]
            
            for domain in youtube_domains:
                assert any(domain in allowed for allowed in ALLOWED_DOMAINS)
        except ImportError:
            pytest.skip("ALLOWED_DOMAINS not implemented")
    
    def test_secret_key_not_default(self):
        """Test que SECRET_KEY no es el default"""
        from server import app
        
        # Should not be the example/default key
        assert app.config.get('SECRET_KEY') != 'change-this-in-production'
        assert app.config.get('SECRET_KEY') != 'dev'
        assert len(app.config.get('SECRET_KEY', '')) > 10
    
    def test_csrf_disabled_in_testing(self):
        """Test que CSRF está deshabilitado en testing"""
        from server import app
        
        if app.config.get('TESTING'):
            assert app.config.get('WTF_CSRF_ENABLED') == False
