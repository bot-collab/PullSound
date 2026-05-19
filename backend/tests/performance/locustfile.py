"""
Performance tests usando Locust
"""
from locust import HttpUser, task, between
API_HEALTH_PATH = "/api/health"
import random


class PullSoundUser(HttpUser):
    """Usuario simulado de PullSound"""
    wait_time = between(1, 3)
    
    def on_start(self):
        """Setup antes de las tareas"""
        self.youtube_urls = [
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "https://www.youtube.com/watch?v=9bZkp7q19f0",
            "https://www.youtube.com/watch?v=jNQXAC9IVRw"
        ]
        self.formats = ['mp3', 'flac', 'wav', 'm4a']
        self.qualities = ['128', '192', '256', '320']
    
    @task(5)
    def get_health(self):
        """Test endpoint de salud"""
        self.client.get(API_HEALTH_PATH, name=API_HEALTH_PATH)
    
    @task(10)
    def get_info(self):
        """Test obtener información de video"""
        url = random.choice(self.youtube_urls)
        self.client.post("/api/info", 
            json={"url": url},
            name="/api/info"
        )
    
    @task(3)
    def download_audio(self):
        """Test descargar audio"""
        url = random.choice(self.youtube_urls)
        format_choice = random.choice(self.formats)
        quality = random.choice(self.qualities)
        
        response = self.client.post("/api/download",
            json={
                "url": url,
                "format": format_choice,
                "quality": quality
            },
            name="/api/download"
        )
        
        # Si se crea la tarea, verificar status
        if response.status_code == 200:
            try:
                data = response.json()
                task_id = data.get('task_id')
                if task_id:
                    self.client.get(f"/api/status/{task_id}",
                        name="/api/status/[id]"
                    )
            except Exception:
                pass
    
    @task(1)
    def get_static_files(self):
        """Test archivos estáticos"""
        static_files = [
            "/robots.txt",
            "/sitemap.xml",
            "/"
        ]
        file = random.choice(static_files)
        self.client.get(file, name=f"static:{file}")


# Configuración para test rápido
class QuickLoadTest(HttpUser):
    """Test rápido de carga"""
    wait_time = between(0.5, 1.5)
    
    @task
    def health_check(self):
        self.client.get(API_HEALTH_PATH)
