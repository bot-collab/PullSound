"""Registro de rutas estáticas (frontend).

Separamos estas rutas de server.py para reducir acoplamiento y tamaño del archivo,
manteniendo exactamente los mismos endpoints.
"""

from __future__ import annotations


def register_static_routes(app, *, frontend_folder, logger):
    """Registra rutas para servir el frontend y assets."""

    from flask import send_from_directory

    @app.route("/")
    def index():
        """Sirve el frontend"""
        try:
            return send_from_directory(frontend_folder, "index.html")
        except Exception as exc:
            logger.error(f"Error sirviendo index.html: {exc}")
            return f"Error: Frontend no encontrado en {frontend_folder}", 404

    @app.route("/robots.txt")
    def robots():
        """Sirve robots.txt para configuración de crawlers"""
        try:
            return send_from_directory(frontend_folder, "robots.txt")
        except Exception as exc:
            logger.error(f"Error sirviendo robots.txt: {exc}")
            return "User-agent: *\nDisallow: /api/", 200

    @app.route("/sitemap.xml")
    def sitemap():
        """Sirve sitemap.xml para indexación de motores de búsqueda"""
        try:
            return send_from_directory(frontend_folder, "sitemap.xml")
        except Exception as exc:
            logger.error(f"Error sirviendo sitemap.xml: {exc}")
            return (
                "<?xml version=\"1.0\" encoding=\"UTF-8\"?>" +
                "<urlset xmlns=\"http://www.sitemaps.org/schemas/sitemap/0.9\"></urlset>",
                200,
            )

    @app.route("/<path:filename>")
    def serve_static(filename):
        """Sirve archivos estáticos"""
        try:
            if not filename.startswith("api/"):
                return send_from_directory(frontend_folder, filename)
        except Exception as exc:
            logger.error(f"Error sirviendo {filename}: {exc}")
        return "Not found", 404
