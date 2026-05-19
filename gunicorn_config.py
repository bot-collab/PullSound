import os

# Obtener puerto de la variable de entorno (Render/Heroku/etc)
port = os.environ.get("PORT", "5000")
bind = f"0.0.0.0:{port}"

# Trabajadores y hilos
# Para SocketIO en modo 'threading', usamos hilos
workers = 1  # SocketIO funciona mejor con 1 worker si no hay Redis/Sticky sessions
threads = 4
worker_class = "gthread"

# Tiempos de espera
timeout = 120
keepalive = 5

# Logging
accesslog = "-"
errorlog = "-"
loglevel = "info"

# Pre-carga de la app
preload_app = True
