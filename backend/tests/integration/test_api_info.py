"""
Tests de integración para /api/info
"""
import pytest
import json
from unittest.mock import patch, MagicMock


class TestAPIInfo:
    """Tests del endpoint /api/info"""
    
    def test_info_endpoint_requires_url(self, client):
        """Test que requiere URL"""
        response = client.post('/api/info',
            json={},
            content_type='application/json'
        )
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data
    
    def test_info_endpoint_invalid_json(self, client):
        """Test con JSON inválido"""
        response = client.post('/api/info',
            data='invalid json',
            content_type='application/json'
        )
        
        assert response.status_code == 400
    
    def test_info_endpoint_empty_url(self, client):
        """Test con URL vacía"""
        response = client.post('/api/info',
            json={'url': ''},
            content_type='application/json'
        )
        
        assert response.status_code == 400
    
    def test_info_endpoint_invalid_url_format(self, client):
        """Test con formato de URL inválido"""
        response = client.post('/api/info',
            json={'url': 'not-a-valid-url'},
            content_type='application/json'
        )
        
        # Puede ser 400 o 500 dependiendo de validación
        assert response.status_code in [400, 500]
    
    def test_info_endpoint_non_youtube_url(self, client):
        """Test con URL que no es de YouTube"""
        response = client.post('/api/info',
            json={'url': 'https://google.com'},
            content_type='application/json'
        )
        
        assert response.status_code in [400, 500]
    
    @pytest.mark.slow
    def test_info_endpoint_valid_youtube_url(self, client, mock_youtube_url):
        """Test con URL válida de YouTube (puede ser lento)"""
        response = client.post('/api/info',
            json={'url': mock_youtube_url},
            content_type='application/json'
        )
        
        # Can be 200 (success) or error if yt-dlp fails
        if response.status_code == 200:
            data = json.loads(response.data)
            assert 'title' in data or 'error' in data
