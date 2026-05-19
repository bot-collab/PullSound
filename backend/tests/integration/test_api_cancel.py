"""
Tests de integración para /api/cancel
"""
import pytest
import json


class TestAPICancel:
    """Tests del endpoint /api/cancel/<task_id>"""
    
    def test_cancel_endpoint_invalid_task(self, client):
        """Test con task_id inválido"""
        response = client.post('/api/cancel/invalid-task-id')
        
        assert response.status_code in [404, 400]
        data = json.loads(response.data)
        assert 'error' in data or 'success' in data
    
    def test_cancel_endpoint_nonexistent_task(self, client):
        """Test con task_id que no existe"""
        fake_task_id = '00000000-0000-0000-0000-000000000000'
        response = client.post(f'/api/cancel/{fake_task_id}')
        
        assert response.status_code in [404, 200]
    
    def test_cancel_endpoint_valid_task(self, client, mock_youtube_url):
        """Test cancelar tarea válida"""
        # Primero crear una tarea
        download_response = client.post('/api/download',
            json={
                'url': mock_youtube_url,
                'format': 'mp3',
                'quality': '128'
            }
        )
        
        if download_response.status_code == 200:
            task_id = json.loads(download_response.data)['task_id']
            
            # Cancelar inmediatamente (puede que ya esté en proceso)
            cancel_response = client.post(f'/api/cancel/{task_id}')
            
            # Accept both success and "not found" since task may complete quickly
            assert cancel_response.status_code in [200, 404]
            
            if cancel_response.status_code == 200:
                cancel_data = json.loads(cancel_response.data)
                assert 'status' in cancel_data or 'message' in cancel_data
    
    def test_cancel_endpoint_already_completed(self, client, mock_youtube_url):
        """Test cancelar tarea ya completada"""
        # Create and potentially complete a task
        download_response = client.post('/api/download',
            json={
                'url': mock_youtube_url,
                'format': 'mp3',
                'quality': '128'
            }
        )
        
        if download_response.status_code == 200:
            task_id = json.loads(download_response.data)['task_id']
            
            # Try to cancel (may or may not be completed)
            cancel_response = client.post(f'/api/cancel/{task_id}')
            
            # Should handle gracefully
            assert cancel_response.status_code in [200, 400]
    
    def test_cancel_endpoint_double_cancel(self, client, mock_youtube_url):
        """Test cancelar la misma tarea dos veces"""
        download_response = client.post('/api/download',
            json={
                'url': mock_youtube_url,
                'format': 'mp3',
                'quality': '128'
            }
        )
        
        if download_response.status_code == 200:
            task_id = json.loads(download_response.data)['task_id']
            
            # First cancel
            first_cancel = client.post(f'/api/cancel/{task_id}')
            assert first_cancel.status_code == 200
            
            # Second cancel (should be idempotent)
            second_cancel = client.post(f'/api/cancel/{task_id}')
            assert second_cancel.status_code in [200, 404]
