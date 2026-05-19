"""Application entry helpers.

Este módulo ofrece una API estable para obtener la app y SocketIO sin acoplar
al resto del código a los detalles de import de server.py.

Nota: en esta versión, `server.py` sigue siendo la fuente de verdad de la app.
El objetivo es permitir una migración gradual hacia un app-factory completo sin
romper compatibilidad.
"""

from __future__ import annotations

import importlib
import sys


def _import_server_module():
    """Importa el módulo server priorizando el nombre plano para coincidir con tests.

    Los tests usan `import server as backend_server`; si importamos `backend.server`
    se cargaría un módulo distinto y la app no sería idéntica. Este helper busca
    primero en sys.modules con la clave 'server', luego intenta importlib.import_module('server').
    Si falla, recurre a `backend.server`.
    """
    if 'server' in sys.modules:
        return sys.modules['server']

    try:
        return importlib.import_module('server')
    except Exception:
        return importlib.import_module('backend.server')


def create_app(*, testing: bool = False, start_background_services: bool = False):
    """Retorna (app, socketio) configurados.

    - Por defecto NO inicia threads/workers: seguro para tests e imports.
    - Si `start_background_services=True`, arranca workers/cleanup thread.
    """
    backend_server = _import_server_module()

    if testing:
        backend_server.app.config["TESTING"] = True

    if start_background_services:
        backend_server.start_background_services()

    return backend_server.app, backend_server.socketio
