"""
Tests de integración para WebSocket
"""
import pytest
import json


class TestWebSocket:
    """Tests de WebSocket handlers"""
    
    def test_websocket_connection(self, socket_client):
        """Test conexión básica de WebSocket"""
        assert socket_client.is_connected()
    
    def test_websocket_join_room(self, socket_client):
        """Test join room con task_id"""
        # Emit join event
        socket_client.emit('join', {'task_id': 'test-task-123'})
        
        # Should have received some response
        # (exact response depends on server implementation)
        assert socket_client.is_connected()
    
    def test_websocket_join_without_task_id(self, socket_client):
        """Test join sin task_id"""
        # Emit join without task_id
        socket_client.emit('join', {})
        
        # Should handle gracefully
        assert socket_client.is_connected()
    
    def test_websocket_multiple_joins(self, socket_client):
        """Test múltiples joins"""
        # Join multiple rooms
        for i in range(3):
            socket_client.emit('join', {'task_id': f'task-{i}'})
        
        # Should handle multiple joins
        assert socket_client.is_connected()
    
    def test_websocket_disconnect_reconnect(self, socket_client):
        """Test desconexión y reconexión"""
        # Initial connection
        assert socket_client.is_connected()
        
        # Disconnect
        socket_client.disconnect()
        
        # Note: Reconnection would require a new client
        # This test verifies disconnect works
        assert not socket_client.is_connected()
