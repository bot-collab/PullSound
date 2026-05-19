"""Handlers de WebSocket (SocketIO).

Mantiene el evento `join` tal cual, pero fuera de server.py.
"""

from __future__ import annotations


def register_websocket_handlers(socketio, *, join_room, emit, downloads_lock, active_downloads, logger):
    """Registra handlers de SocketIO."""

    @socketio.on("join")
    def on_join(data):
        # Compat: algunos clientes usan taskId (frontend), otros task_id (tests)
        room = data.get("taskId") or data.get("task_id")
        if room:
            join_room(room)
            logger.info(f"Cliente unido a sala: {room}")
            with downloads_lock:
                if room in active_downloads:
                    emit("status_update", active_downloads[room], room=room)
