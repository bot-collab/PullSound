"""
Tests unitarios para funciones de workers
"""
import pytest
import time
from unittest.mock import Mock, patch, MagicMock


class TestDownloadWorker:
    """Tests de funciones relacionadas con workers"""
    
    def test_download_task_creation(self):
        """Test creación de DownloadTask"""
        from server import DownloadTask
        
        task = DownloadTask(
            task_id='test-123',
            url='https://youtube.com/watch?v=test',
            audio_format='mp3',
            quality='320'
        )
        
        assert task.task_id == 'test-123'
        assert task.url == 'https://youtube.com/watch?v=test'
        assert task.audio_format == 'mp3'
        assert task.quality == '320'
        assert task.status == 'queued'
        assert task.progress == 0
        assert task.error is None
    
    def test_download_task_attributes(self):
        """Test atributos de DownloadTask"""
        from server import DownloadTask
        
        task = DownloadTask('id', 'url', 'flac', '256')
        
        # Verify all required attributes exist
        assert hasattr(task, 'task_id')
        assert hasattr(task, 'url')
        assert hasattr(task, 'audio_format')
        assert hasattr(task, 'quality')
        assert hasattr(task, 'status')
        assert hasattr(task, 'progress')
        assert hasattr(task, 'message')
        assert hasattr(task, 'error')
        assert hasattr(task, 'filename')
        assert hasattr(task, 'title')
        assert hasattr(task, 'created_at')
    
    def test_check_cancellation_function(self):
        """Test función check_cancellation"""
        from server import check_cancellation, cancel_events
        
        # Test with non-existent task
        result = check_cancellation('nonexistent-task')
        assert result is False
        
        # Test with cancelled task
        from threading import Event
        test_event = Event()
        test_event.set()  # Mark as cancelled
        cancel_events['test-cancelled'] = test_event
        
        result = check_cancellation('test-cancelled')
        assert result is True
        
        # Cleanup
        del cancel_events['test-cancelled']
    
    def test_update_task_progress_function(self):
        """Test función update_task_progress"""
        from server import update_task_progress, active_downloads
        import threading
        
        # Create a test task
        task_id = 'test-progress-123'
        active_downloads[task_id] = {
            'status': 'queued',
            'progress': 0,
            'message': 'Waiting'
        }
        
        # Update progress
        update_task_progress(task_id, 'downloading', 50, 'Downloading...')
        
        # Verify update
        assert active_downloads[task_id]['status'] == 'downloading'
        assert active_downloads[task_id]['progress'] == 50
        assert active_downloads[task_id]['message'] == 'Downloading...'
        
        # Cleanup
        del active_downloads[task_id]
    
    def test_sanitize_input_function(self):
        """Test función sanitize_input"""
        from server import sanitize_input
        
        # Normal input
        result = sanitize_input("normal text", max_length=100)
        assert result == "normal text"
        
        # Long input (should truncate)
        long_text = "a" * 300
        result = sanitize_input(long_text, max_length=100)
        assert len(result) <= 100
        
        # Empty input
        result = sanitize_input("", max_length=100)
        assert result == ""
    
    def test_validate_youtube_url_function(self):
        """Test función validate_youtube_url"""
        from server import validate_youtube_url
        
        # Valid YouTube URLs
        valid_urls = [
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "https://youtu.be/dQw4w9WgXcQ",
            "https://m.youtube.com/watch?v=test"
        ]
        
        for url in valid_urls:
            assert validate_youtube_url(url) is True
        
        # Invalid URLs
        invalid_urls = [
            "https://google.com",
            "not-a-url",
            "",
            "javascript:alert(1)"
        ]
        
        for url in invalid_urls:
            assert validate_youtube_url(url) is False
    
    def test_generate_chunks_function(self):
        """Test función generate_chunks"""
        from server import generate_chunks
        from pathlib import Path
        import tempfile
        
        # Create a temporary file
        with tempfile.NamedTemporaryFile(delete=False, mode='wb') as f:
            test_data = b"test data " * 100
            f.write(test_data)
            temp_path = Path(f.name)
        
        try:
            # Test chunk generation
            chunks = list(generate_chunks(temp_path, chunk_size=50))
            
            # Verify chunks were generated
            assert len(chunks) > 0
            
            # Verify total size matches
            total_size = sum(len(chunk) for chunk in chunks)
            assert total_size == len(test_data)
        finally:
            # Cleanup
            temp_path.unlink()
