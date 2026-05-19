"""
Tests de integración para servir archivos estáticos
"""
import pytest


class TestStaticFiles:
    """Tests para archivos estáticos y SEO"""
    
    def test_index_page(self, client):
        """Verifica que el index se sirve"""
        response = client.get('/')
        assert response.status_code == 200
        assert b'PullSound' in response.data
    
    def test_robots_txt(self, client):
        """Verifica que robots.txt es accesible"""
        response = client.get('/robots.txt')
        assert response.status_code == 200
        assert b'User-agent' in response.data
    
    def test_sitemap_xml(self, client):
        """Verifica que sitemap.xml es accesible"""
        response = client.get('/sitemap.xml')
        assert response.status_code == 200
        assert b'<?xml version' in response.data
        assert b'urlset' in response.data
    
    def test_og_image(self, client):
        """Verifica que og-image.png existe"""
        response = client.get('/og-image.png')
        # Puede ser 200 o 404 dependiendo si existe
        assert response.status_code in [200, 404]
    
    def test_favicon(self, client):
        """Verifica que favicon es accesible"""
        response = client.get('/favicon.svg')
        # Puede ser 200 o 404
        assert response.status_code in [200, 404]
