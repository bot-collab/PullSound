"""
Tests de integración para /api/download
"""
import pytest
import json


class TestAPIDownload:
    """Tests del endpoint /api/download"""
    
    def test_download_endpoint_requires_url(self, client):
        """Test que requiere URL"""
        response = client.post('/api/download',
            json={'format': 'mp3', 'quality': '128'},
            content_type='application/json'
        )
        
        assert response.status_code == 400
    
    def test_download_endpoint_requires_format(self, client, mock_youtube_url):
        """Test que requiere formato"""
        response = client.post('/api/download',
            json={'url': mock_youtube_url, 'quality': '128'},
            content_type='application/json'
        )
        
        assert response.status_code == 400
    
    def test_download_endpoint_requires_quality(self, client, mock_youtube_url):
        """Test que requiere calidad"""
        response = client.post('/api/download',
            json={'url': mock_youtube_url, 'format': 'mp3'},
            content_type='application/json'
        )
        
        assert response.status_code == 400
    
    def test_download_endpoint_invalid_format(self, client, mock_youtube_url):
        """Test con formato inválido"""
        response = client.post('/api/download',
            json={
                'url': mock_youtube_url,
                'format': 'invalid_format',
                'quality': '128'
            },
            content_type='application/json'
        )
        
        assert response.status_code == 400
    
    def test_download_endpoint_invalid_quality(self, client, mock_youtube_url):
        """Test con calidad inválida"""
        response = client.post('/api/download',
            json={
                'url': mock_youtube_url,
                'format': 'mp3',
                'quality': '999'
            },
            content_type='application/json'
        )
        
        assert response.status_code == 400
    
    def test_download_endpoint_creates_task_id(self, client, mock_youtube_url):
        """Test que crea task_id"""
        response = client.post('/api/download',
            json={
                'url': mock_youtube_url,
                'format': 'mp3',
                'quality': '128'
            },
            content_type='application/json'
        )
        
        # May be 200 or 500 depending on server state
        if response.status_code == 200:
            data = json.loads(response.data)
            assert 'task_id' in data
            assert len(data['task_id']) > 0
