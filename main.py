#!/usr/bin/env python3
"""
YouTube Audio Converter - Inicializador Principal
Autor: 3sc0b0t
Fecha: 2025-10-15
"""

# NOTE: Removed eventlet.monkey_patch() - it conflicts with FFmpeg subprocess on Windows
# Using threading mode instead for SocketIO

import sys
import os
import subprocess
import platform
from pathlib import Path
import importlib.util

# Colores para la terminal
class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

def print_banner():
    """Muestra el banner de inicio"""
    # Import config for project info
    try:
        from backend import config
        project_date = config.PROJECT_INFO['date']
        project_version = config.PROJECT_INFO['version']
    except Exception:
        project_date = "2025-10-15"
        project_version = "1.0.0"
    
    banner = f"""
{Colors.HEADER}{Colors.BOLD}
╔═══════════════════════════════════════════════════════╗
║                                                       ║
║               YOUTUBE AUDIO CONVERTER                 ║
║                                                       ║
║     Convertidor de YouTube a MP3/FLAC/WAV             ║
║     Desarrollado por: 3sc0b0t                         ║
║     Versión: {project_version} - Fecha: {project_date}    ║
║                                                       ║
╚═══════════════════════════════════════════════════════╝
{Colors.ENDC}
    """
    print(banner)

def check_python_version():
    """Verifica la versión de Python"""
    print(f"{Colors.OKBLUE}[1/5] Verificando versión de Python...{Colors.ENDC}")
    
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 14):
        print(f"{Colors.FAIL} Error: Se requiere Python 3.14 o superior{Colors.ENDC}")
        print(f"  Versión actual: {sys.version}")
        return False
    
    print(f"{Colors.OKGREEN} Python {version.major}.{version.minor}.{version.micro} detectado{Colors.ENDC}")
    return True

def check_ffmpeg():
    """Verifica si FFmpeg está instalado"""
    print(f"\n{Colors.OKBLUE}[2/5] Verificando FFmpeg...{Colors.ENDC}")
    
    try:
        result = subprocess.run(
            ['ffmpeg', '-version'],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        if result.returncode == 0:
            version_line = result.stdout.split('\n')[0]
            print(f"{Colors.OKGREEN} FFmpeg detectado: {version_line}{Colors.ENDC}")
            return True
        else:
            raise RuntimeError("FFmpeg no responde correctamente")
            
    except (subprocess.TimeoutExpired, FileNotFoundError, RuntimeError) as e:
        print(f"{Colors.FAIL}x Error al detectar FFmpeg: {str(e)}{Colors.ENDC}")
        print(f"\n{Colors.WARNING}FFmpeg es CRÍTICO para convertir audio.{Colors.ENDC}")
        
        system = platform.system()
        if system == "Windows":
            print("  • Opción 1: Instala con Chocolatey: choco install ffmpeg")
            print("  • Opción 2: Descarga de https://www.gyan.dev/ffmpeg/builds/ y añade al PATH")
        elif system == "Darwin":  # macOS
            print("  • Instala con Homebrew: brew install ffmpeg")
        else:  # Linux
            print("  • Ubuntu/Debian: sudo apt update && sudo apt install -y ffmpeg")
            print("  • Docker: Asegúrate de que el Dockerfile incluya 'apt-get install -y ffmpeg'")
        
        return False

def check_dependencies():
    """Verifica e instala las dependencias de Python"""
    print(f"\n{Colors.OKBLUE}[3/5] Verificando dependencias de Python...{Colors.ENDC}")
    
    required_packages = {
        'flask': 'Flask',
        'flask_cors': 'flask-cors',
        'yt_dlp': 'yt-dlp',
        'flask_socketio': 'flask-socketio',
        'eventlet': 'eventlet'
    }
    
    missing_packages = []
    
    for module_name, package_name in required_packages.items():
        if importlib.util.find_spec(module_name) is None:
            missing_packages.append(package_name)
            print(f"{Colors.WARNING}  ○ {package_name} - No instalado{Colors.ENDC}")
        else:
            print(f"{Colors.OKGREEN}  ✓ {package_name} - Instalado{Colors.ENDC}")
    
    if missing_packages:
        print(f"\n{Colors.WARNING}Instalando paquetes faltantes...{Colors.ENDC}")
        
        try:
            subprocess.check_call([
                sys.executable, 
                '-m', 
                'pip', 
                'install', 
                '--upgrade',
                *missing_packages
            ])
            print(f"{Colors.OKGREEN}> Dependencias instaladas correctamente{Colors.ENDC}")
            return True
        except subprocess.CalledProcessError:
            print(f"{Colors.FAIL}x Error al instalar dependencias{Colors.ENDC}")
            print(f"  Intenta manualmente: pip install {' '.join(missing_packages)}")
            return False
    
    print(f"{Colors.OKGREEN}> Todas las dependencias estan instaladas{Colors.ENDC}")
    return True

def setup_directories():
    """Crea la estructura de directorios necesaria"""
    print(f"\n{Colors.OKBLUE}[4/5] Configurando directorios...{Colors.ENDC}")
    
    base_dir = Path(__file__).parent
    backend_dir = base_dir / 'backend'
    downloads_dir = backend_dir / 'downloads'
    frontend_dir = base_dir / 'frontend'
    
    # Crear directorios
    try:
        backend_dir.mkdir(exist_ok=True, parents=True)
        downloads_dir.mkdir(exist_ok=True, parents=True)
        frontend_dir.mkdir(exist_ok=True, parents=True)
        
        # Verificar permisos de escritura en downloads
        test_file = downloads_dir / '.write_test'
        try:
            test_file.touch()
            test_file.unlink()
            print(f"{Colors.OKGREEN}> Estructura de directorios verificada (Escritura OK){Colors.ENDC}")
        except (PermissionError, IOError):
            print(f"{Colors.FAIL}x Error: No hay permisos de escritura en {downloads_dir}{Colors.ENDC}")
            print(f"{Colors.WARNING}  Esto impedirá guardar los archivos descargados.{Colors.ENDC}")
            
    except Exception as e:
        print(f"{Colors.FAIL}x Error al crear directorios: {str(e)}{Colors.ENDC}")
        return None, None, None
    
    print(f"  • Backend: {backend_dir}")
    print(f"  • Downloads: {downloads_dir}")
    print(f"  • Frontend: {frontend_dir}")
    
    return backend_dir, downloads_dir, frontend_dir

def get_runtime_port(default: int = 5000) -> int:
    """Obtiene el puerto desde PORT/SERVER_PORT; si es inválido, usa default."""

    raw = os.environ.get("PORT") or os.environ.get("SERVER_PORT")
    if raw:
        cleaned = raw.strip()
        if cleaned.startswith("$"):
            cleaned = ""  # Render: evitar placeholders tipo "$PORT"
        try:
            return int(cleaned)
        except (ValueError, TypeError):
            print(f"{Colors.WARNING}⚠️ PORT inválido ('{raw}'), usando {default}{Colors.ENDC}")
    return default

def start_server():
    """Inicia el servidor Flask"""
    print(f"\n{Colors.OKBLUE}[5/5] Iniciando servidor...{Colors.ENDC}")
    
    base_dir = Path(__file__).parent
    backend_dir = base_dir / 'backend'
    server_file = backend_dir / 'server.py'
    port = get_runtime_port()
    
    if not server_file.exists():
        print(f"{Colors.FAIL}x Error: No se encuentra backend/server.py{Colors.ENDC}")
        print(f"  Asegúrate de tener el archivo server.py en: {backend_dir}")
        return False
    
    print(f"\n{Colors.OKGREEN}{Colors.BOLD}{'='*60}{Colors.ENDC}")
    print(f"{Colors.OKGREEN}{Colors.BOLD}  Servidor iniciado correctamente{Colors.ENDC}")
    print(f"{Colors.OKGREEN}{Colors.BOLD}{'='*60}{Colors.ENDC}")
    print(f"\n{Colors.OKCYAN}📡 URL del servidor: {Colors.BOLD}http://localhost:{port}{Colors.ENDC}")
    print(f"{Colors.OKCYAN}🌐 Frontend: Abre {Colors.BOLD}frontend/index.html{Colors.ENDC} en tu navegador")
    print(f"\n{Colors.WARNING}Presiona Ctrl+C para detener el servidor{Colors.ENDC}\n")
    
    try:
        # Asegurar imports absolutos para linters y ejecución
        sys.path.insert(0, str(base_dir))
        # Importar y ejecutar el servidor
        from backend.application import create_app
        app, socketio = create_app(start_background_services=True)
        
        # Ejecutar el servidor con SocketIO (necesario para eventlet)
        socketio.run(
            app,
            debug=False,
            port=port,
            host='0.0.0.0',
            use_reloader=False,
            log_output=True,
            allow_unsafe_werkzeug=True  # Needed on Render (threading mode)
        )
        
    except KeyboardInterrupt:
        print(f"\n\n{Colors.WARNING}Servidor detenido por el usuario{Colors.ENDC}")
        return True
    except Exception as e:
        print(f"\n{Colors.FAIL}x Error al iniciar el servidor: {str(e)}{Colors.ENDC}")
        return False

def show_help():
    """Muestra la ayuda del comando"""
    help_text = f"""
{Colors.OKCYAN}Uso:{Colors.ENDC}
    python main.py [opciones]

{Colors.OKCYAN}Opciones:{Colors.ENDC}
    --help, -h          Muestra esta ayuda
    --check, -c         Solo verifica las dependencias sin iniciar
    --install, -i       Instala las dependencias faltantes
    --version, -v       Muestra la versión

{Colors.OKCYAN}Ejemplos:{Colors.ENDC}
    python main.py              # Inicia el servidor
    python main.py --check      # Solo verifica dependencias
    python main.py --install    # Instala dependencias
    """
    print(help_text)

def main():
    """Función principal"""
    
    # Procesar argumentos
    if len(sys.argv) > 1:
        arg = sys.argv[1].lower()
        
        if arg in ['--help', '-h']:
            show_help()
            return
        
        elif arg in ['--version', '-v']:
            print("YouTube Audio Converter v1.0.0")
            print("Desarrollado por: 3sc0b0t")
            print(f"Python: {sys.version}")
            return
        
        elif arg in ['--check', '-c']:
            print_banner()
            check_python_version()
            check_ffmpeg()
            check_dependencies()
            return
        
        elif arg in ['--install', '-i']:
            print_banner()
            if check_python_version():
                check_dependencies()
            return
    
    # Flujo normal de inicio
    print_banner()
    
    # Paso 1: Verificar Python
    if not check_python_version():
        sys.exit(1)
    
    # Paso 2: Verificar FFmpeg
    if not check_ffmpeg():
        print(f"\n{Colors.WARNING}¿Deseas continuar sin FFmpeg? (no se podrá convertir audio) [s/N]: {Colors.ENDC}", end='')
        response = input().lower()
        if response not in ['s', 'si', 'yes', 'y']:
            sys.exit(1)
    
    # Paso 3: Verificar/Instalar dependencias
    if not check_dependencies():
        sys.exit(1)
    
    # Paso 4: Configurar directorios
    setup_directories()
    
    # Paso 5: Iniciar servidor
    start_server()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n\n{Colors.WARNING}Programa interrumpido por el usuario{Colors.ENDC}")
        sys.exit(0)
    except Exception as e:
        print(f"\n{Colors.FAIL}Error fatal: {str(e)}{Colors.ENDC}")
        sys.exit(1)