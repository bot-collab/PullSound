#!/usr/bin/env python3
"""
Script para actualizar todas las dependencias del proyecto
"""

import subprocess
import sys

def update_all():
    """Actualiza todas las dependencias"""
    packages = [
        'Flask',
        'flask-cors', 
        'yt-dlp',
        'pip',
        'setuptools',
        'wheel'
    ]
    
    print("Actualizando dependencias...\n")
    
    for package in packages:
        print(f"Actualizando {package}...")
        try:
            subprocess.check_call([
                sys.executable,
                '-m',
                'pip',
                'install',
                '--upgrade',
                package
            ])
            print(f"✓ {package} actualizado\n")
        except subprocess.CalledProcessError:
            print(f"Error actualizando {package}\n")

if __name__ == "__main__":
    update_all()
    print("Actualización completada!")