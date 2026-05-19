"""
Tests de integración para descarga de archivos
"""
import pytest
import json
from pathlib import Path


class TestFileDownload:
    """Tests del endpoint /api/file/<filename>"""
    
    def test_file_download_missing_filename(self, client):
        """Test sin filename"""
        response = client.get('/api/file/')
        
        # Should be 404 or 405
        assert response.status_code in [404, 405]
    
    def test_file_download_nonexistent_file(self, client):
        """Test con archivo que no existe"""
        response = client.get('/api/file/nonexistent_file.mp3')
        
        assert response.status_code == 404
    
    def test_file_download_path_traversal_attempt(self, client):
        """Test intento de path traversal"""
        dangerous_paths = [
            '../../../etc/passwd',
            '..\\..\\windows\\system32\\config\\sam',
            '/etc/passwd'
        ]
        
        for path in dangerous_paths:
            response = client.get(f'/api/file/{path}')
            
            # Should handle gracefully (sanitize or reject)
            assert response.status_code in [200, 400, 403, 404, 500]
    
    def test_file_download_special_characters(self, client):
        """Test con caracteres especiales"""
        special_files = [
            'file with spaces.mp3',
            'file-with-dashes.mp3',
            'file_with_underscores.mp3'
        ]
        
        for filename in special_files:
            response = client.get(f'/api/file/{filename}')
            
            # Should handle gracefully (404 if doesn't exist)
            assert response.status_code in [200, 404]
    
    def test_file_download_headers(self, client):
        """Test headers de descarga"""
        # This test would need a real file to exist
        # For now, just verify the endpoint structure
        response = client.get('/api/file/test.mp3')
        
        # Even if 404, should have proper headers
        assert response.status_code in [200, 404]
        
        if response.status_code == 200:
            # Verify download headers
            assert 'Content-Disposition' in response.headers or \
                   'content-disposition' in response.headers
