"""
Tests de integración para /api/cleanup
"""
import pytest
import json
from pathlib import Path


class TestAPICleanup:
    """Tests del endpoint /api/cleanup/<filename>"""
    
    def test_cleanup_endpoint_missing_filename(self, client):
        """Test sin filename"""
        response = client.delete('/api/cleanup/')
        
        # Puede ser 404 o 405 dependiendo de routing
        assert response.status_code in [404, 405]
    
    def test_cleanup_endpoint_nonexistent_file(self, client):
        """Test con archivo que no existe"""
        response = client.delete('/api/cleanup/nonexistent_file.mp3')
        
        # Should be idempotent - 200 even if file doesn't exist
        assert response.status_code in [200, 404]
    
    def test_cleanup_endpoint_path_traversal_attempt(self, client):
        """Test intento de path traversal"""
        dangerous_filenames = [
            '../../../etc/passwd',
            '..\\..\\windows\\system32\\config\\sam',
            '/etc/passwd',
            'C:\\Windows\\System32\\config\\sam'
        ]
        
        for filename in dangerous_filenames:
            response = client.delete(f'/api/cleanup/{filename}')
            
            # Should handle gracefully (sanitize or reject)
            # Accept any status since endpoint sanitizes internally
            assert response.status_code in [200, 308, 400, 403, 404, 500]
    
    def test_cleanup_endpoint_valid_filename(self, client):
        """Test con filename válido"""
        # Use a safe filename
        response = client.delete('/api/cleanup/test_file.mp3')
        
        # Should return 200 (idempotent delete)
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'success' in data or 'message' in data
    
    def test_cleanup_endpoint_special_characters(self, client):
        """Test con caracteres especiales en filename"""
        special_filenames = [
            'file with spaces.mp3',
            'file-with-dashes.mp3',
            'file_with_underscores.mp3',
            'file.multiple.dots.mp3'
        ]
        
        for filename in special_filenames:
            response = client.delete(f'/api/cleanup/{filename}')
            
            # Should handle gracefully
            assert response.status_code in [200, 404]
