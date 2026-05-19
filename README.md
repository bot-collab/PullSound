# PullSound 🎵

![Version](https://img.shields.io/badge/version-1.0.0-blue)
![Python](https://img.shields.io/badge/python-3.8+-green)
![License](https://img.shields.io/badge/license-MIT-yellow)

Download audio from YouTube, SoundCloud, and more. Convert to MP3, FLAC, WAV, M4A, OPUS with high quality.

## ✨ Características

- 🎯 **Múltiples formatos**: MP3, FLAC, WAV, M4A, OPUS
- 📊 **Progreso en tiempo real** con WebSockets
- 📝 **Soporte para playlists** con descarga individual o masiva
- 🎨 **Interfaz moderna** con animaciones fluidas
- ⚡ **Descargas concurrentes** (hasta 5 simultáneas)
- 🛑 **Cancelación instantánea** de descargas
- 🧹 **Limpieza automática** de archivos antiguos

## 📋 Requisitos Previos

### Sistema Operativo

- Windows 10/11
- Linux (Ubuntu 20.04+, Fedora 35+)
- macOS (11+)

### Software Requerido

1. **Python 3.14 o superior**

   ```bash
   python --version  # Verificar instalación
   ```

2. **FFmpeg** (esencial para conversión de audio)

   **Windows:**

   ```bash
   # Con Chocolatey
   choco install ffmpeg

   # O descargar desde: https://www.gyan.dev/ffmpeg/builds/
   ```

   **macOS:**

   ```bash
   brew install ffmpeg
   ```

   **Linux:**

   ```bash
   # Ubuntu/Debian
   sudo apt install ffmpeg

   # Fedora
   sudo dnf install ffmpeg
   ```

## 🚀 Instalación

### 1. Clonar el repositorio

```bash
git clone https://github.com/tuusuario/spydonw.git
cd spydonw
```

### 2. Crear entorno virtual (recomendado)

```bash
python -m venv .spydonw
source .spydonw/bin/activate  # Linux/macOS
.spydonw\Scripts\activate     # Windows
```

### 3. Instalar dependencias

```bash
pip install -r requirements.txt
```

**O instalación automática:**

```bash
python main.py --install
```

## 💻 Uso

### Inicio Rápido

```bash
python main.py
```

El servidor se iniciará en `http://localhost:5000`. Abre tu navegador y accede a esa URL.

### Opciones de Línea de Comandos

```bash
python main.py [opciones]
```

| Opción            | Descripción                       |
| ----------------- | --------------------------------- |
| `--help`, `-h`    | Muestra ayuda                     |
| `--check`, `-c`   | Verifica dependencias sin iniciar |
| `--install`, `-i` | Instala dependencias faltantes    |
| `--version`, `-v` | Muestra versión                   |

### Ejemplos de Uso

**Descargar un video:**

1. Pega la URL de YouTube
2. Selecciona formato (MP3, FLAC, etc.)
3. Selecciona calidad (128kbps, 320kbps, etc.)
4. Haz clic en "Descargar"

**Descargar playlist completa:**

1. Pega URL de playlist de YouTube
2. Aparecerán todas las canciones
3. Descarga individualmente o usa "Descargar Todo"

## 📁 Estructura del Proyecto

```
spydonw/
├── backend/
│   ├── config.py          # Configuración centralizada
│   ├── server.py          # Servidor Flask + SocketIO
│   └── downloads/         # Archivos descargados (temporal)
├── frontend/
│   ├── index.html         # Interfaz web
│   ├── script.js          # Lógica del cliente
│   └── styles.css         # Estilos
├── main.py                # Punto de entrada
├── requirements.txt       # Dependencias Python
└── README.md             # Este archivo
```

## ⚙️ Configuración

Edita `backend/config.py` para personalizar:

```python
# Tiempo de limpieza automática
CLEANUP_DELAY = 300  # 5 minutos

# Edad máxima de archivos
FILE_MAX_AGE = 1800  # 30 minutos

# Descargas concurrentes
MAX_CONCURRENT_DOWNLOADS = 5

# Puerto del servidor
SERVER_PORT = 5000
```

## 🔧 Tecnologías

### Backend

- **Flask**: Framework web
- **Flask-SocketIO**: Comunicación en tiempo real
- **yt-dlp**: Motor de descarga de YouTube
- **FFmpeg**: Conversión de audio

### Frontend

- **Vanilla JavaScript**: Sin frameworks
- **WebSockets**: Actualizaciones en vivo
- **CSS Animations**: Barras de progreso animadas

## 🐛 Solución de Problemas

### Error: "FFmpeg no está instalado"

- **Solución**: Instala FFmpeg siguiendo las instrucciones de [Requisitos Previos](#software-requerido)

### Error: "ModuleNotFoundError"

- **Solución**:
  ```bash
  pip install -r requirements.txt
  ```

### El progreso no avanza

- **Solución**: Verifica la consola del navegador (F12) y los logs del servidor
- Asegúrate de que WebSockets esté habilitado en tu firewall

### Descarga muy lenta

- **Problema**: YouTube limita velocidad por IP
- **Solución**: Espera unos minutos entre descargas masivas

## 🚨 Problemas Conocidos

Ver [analisis_errores.md](file:///C:/Users/USUARIO/.gemini/antigravity/brain/405ac77f-adad-49bc-b59e-24e69796912d/analisis_errores.md) para lista completa de issues y roadmap de fixes.

## 📜 Licencia

MIT License - ver archivo LICENSE para detalles

## 👤 Autor

**3sc0b0t**

- Versión: 1.0.0
- Fecha: 2025-10-15

## 🤝 Contribuir

Las contribuciones son bienvenidas. Por favor:

1. Fork el proyecto
2. Crea una rama (`git checkout -b feature/AmazingFeature`)
3. Commit tus cambios (`git commit -m 'Add some AmazingFeature'`)
4. Push a la rama (`git push origin feature/AmazingFeature`)
5. Abre un Pull Request

## ⚠️ Disclaimer

Este software es solo para uso educativo y personal. Respeta los términos de servicio de YouTube y las leyes de derechos de autor de tu país.

---

**¿Problemas?** Abre un issue en GitHub o contacta al autor.
