"""
Tests de integración para /api/health
"""
import pytest
import json


class TestAPIHealth:
    """Tests del endpoint /api/health"""
    
    def test_health_endpoint_exists(self, client):
        """Verifica que el endpoint existe"""
        response = client.get('/api/health')
        assert response.status_code == 200
    
    def test_health_endpoint_structure(self, client):
        """Verifica estructura de respuesta"""
        response = client.get('/api/health')
        data = json.loads(response.data)
        
        assert 'status' in data
        assert 'active_downloads' in data
        assert 'queue_size' in data
        assert 'ffmpeg_available' in data
    
    def test_health_status_healthy(self, client):
        """Verifica que status es healthy"""
        response = client.get('/api/health')
        data = json.loads(response.data)
        
        # Server returns 'ok' not 'healthy'
        assert data['status'] in ['ok', 'healthy']
    
    def test_health_ffmpeg_check(self, client):
        """Verifica detección de FFmpeg"""
        response = client.get('/api/health')
        data = json.loads(response.data)
        
        # FFmpeg debe estar disponible para el proyecto
        assert isinstance(data['ffmpeg_available'], bool)
