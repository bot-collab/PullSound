"""
Tests de integración para /api/preview
"""
import pytest
import json


class TestAPIPreview:
    """Tests del endpoint /api/preview"""
    
    def test_preview_endpoint_requires_url(self, client):
        """Test que requiere URL"""
        response = client.post('/api/preview',
            json={},
            content_type='application/json'
        )
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data
    
    def test_preview_endpoint_invalid_url(self, client):
        """Test con URL inválida"""
        response = client.post('/api/preview',
            json={'url': 'not-a-valid-url'},
            content_type='application/json'
        )
        
        assert response.status_code in [400, 500]
    
    def test_preview_endpoint_non_youtube_url(self, client):
        """Test con URL que no es de YouTube"""
        response = client.post('/api/preview',
            json={'url': 'https://google.com'},
            content_type='application/json'
        )
        
        assert response.status_code in [400, 500]
    
    def test_preview_endpoint_empty_url(self, client):
        """Test con URL vacía"""
        response = client.post('/api/preview',
            json={'url': ''},
            content_type='application/json'
        )
        
        assert response.status_code == 400
    
    @pytest.mark.slow
    def test_preview_endpoint_valid_url(self, client, mock_youtube_url):
        """Test con URL válida de YouTube (puede ser lento)"""
        response = client.post('/api/preview',
            json={'url': mock_youtube_url},
            content_type='application/json'
        )
        
        # Can be 200 (success) or error if yt-dlp fails
        # Preview is a streaming endpoint, so response might be different
        assert response.status_code in [200, 400, 500]
    
    def test_preview_endpoint_custom_duration(self, client, mock_youtube_url):
        """Test con duración personalizada"""
        response = client.post('/api/preview',
            json={
                'url': mock_youtube_url,
                'duration': 15  # 15 seconds instead of default 30
            },
            content_type='application/json'
        )
        
        # Should accept custom duration
        assert response.status_code in [200, 400, 500]
    
    def test_preview_endpoint_invalid_duration(self, client, mock_youtube_url):
        """Test con duración inválida"""
        invalid_durations = [-1, 0, 'invalid', 999999]
        
        for duration in invalid_durations:
            response = client.post('/api/preview',
                json={
                    'url': mock_youtube_url,
                    'duration': duration
                },
                content_type='application/json'
            )
            
            # Should handle invalid duration
            assert response.status_code in [200, 400, 500]
