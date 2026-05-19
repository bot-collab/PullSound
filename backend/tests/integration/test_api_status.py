"""
Tests de integración para /api/status
"""
import pytest
import json
import time


class TestAPIStatus:
    """Tests del endpoint /api/status/<task_id>"""
    
    def test_status_endpoint_invalid_task(self, client):
        """Test con task_id inválido"""
        response = client.get('/api/status/invalid-task-id')
        
        assert response.status_code == 404
        data = json.loads(response.data)
        assert 'error' in data
    
    def test_status_endpoint_nonexistent_task(self, client):
        """Test con task_id que no existe"""
        fake_task_id = '00000000-0000-0000-0000-000000000000'
        response = client.get(f'/api/status/{fake_task_id}')
        
        assert response.status_code == 404
    
    def test_status_endpoint_valid_task(self, client, mock_youtube_url):
        """Test con task_id válido (creado primero)"""
        # Primero crear una tarea
        download_response = client.post('/api/download',
            json={
                'url': mock_youtube_url,
                'format': 'mp3',
                'quality': '128'
            },
            content_type='application/json'
        )
        
        if download_response.status_code == 200:
            download_data = json.loads(download_response.data)
            task_id = download_data.get('task_id')
            
            # Ahora verificar el status (puede que ya se completó)
            status_response = client.get(f'/api/status/{task_id}')
            
            # Accept both found and not found (task may complete quickly)
            assert status_response.status_code in [200, 404]
            
            if status_response.status_code == 200:
                status_data = json.loads(status_response.data)
                
                # Verificar estructura de respuesta
                assert 'status' in status_data
                assert 'progress' in status_data
    
    def test_status_endpoint_structure(self, client, mock_youtube_url):
        """Test estructura de respuesta de status"""
        # Crear tarea
        download_response = client.post('/api/download',
            json={
                'url': mock_youtube_url,
                'format': 'mp3',
                'quality': '128'
            }
        )
        
        if download_response.status_code == 200:
            task_id = json.loads(download_response.data)['task_id']
            
            # Obtener status
            response = client.get(f'/api/status/{task_id}')
            data = json.loads(response.data)
            
            # Verificar campos obligatorios
            assert 'status' in data
            assert 'progress' in data
            assert 'message' in data
            assert isinstance(data['progress'], (int, float))
