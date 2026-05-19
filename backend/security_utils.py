"""Utilities de seguridad (validación/sanitización).

Diseñado para ser usado por el servidor sin crear dependencias circulares.
"""

from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urlparse


def validate_media_url(url: str, allowed_domains: list[str]) -> tuple[bool, str | None]:
    """Valida URL contra whitelist de dominios y bloquea IPs privadas (SSRF protection)."""
    try:
        parsed = urlparse(url)

        # 1) Protocolo debe ser http/https
        if parsed.scheme not in ["http", "https"]:
            return False, "Solo se permiten URLs HTTP/HTTPS"

        # 2) Dominio debe estar en whitelist
        domain = (parsed.netloc or "").lower().lstrip("www.")
        allowed = any(domain.endswith(d) or domain == d for d in allowed_domains)
        if not allowed:
            return False, f"Dominio no permitido: {domain}"

        # 3) No URLs locales/privadas
        hostname = parsed.hostname or ""
        if hostname in ["localhost", "127.0.0.1", "0.0.0.0", "::1"]:
            return False, "URLs locales no permitidas"

        # 4) No redes privadas IPv4
        # Nota: regex en forma raw-string (sin doble-escape) para que coincida con '10.' etc.
        if re.match(r"^(10\.|172\.(1[6-9]|2\d|3[01])\.|192\.168\.)", hostname):
            return False, "IPs privadas no permitidas"

        # 5) No redes privadas IPv6 (fc00::/7, fe80::/10)
        if re.match(r"^(fc00:|fd00:|fe80:)", hostname.lower()):
            return False, "IPs privadas IPv6 no permitidas"

        # 6) No link-local IPv4 (169.254.x.x)
        if hostname.startswith("169.254."):
            return False, "IPs link-local no permitidas"

        return True, None

    except Exception as exc:  # pragma: no cover (defensivo)
        return False, f"URL inválida: {exc}"


def validate_youtube_url(url: str, *, max_url_length: int, allowed_domains: list[str], logger=None) -> bool:
    """Valida URLs (YouTube/SoundCloud según whitelist) con protección SSRF."""
    if not url or not isinstance(url, str):
        return False

    if len(url) > max_url_length:
        if logger:
            logger.warning("URL too long: %s chars", len(url))
        return False

    is_valid, error_msg = validate_media_url(url, allowed_domains)
    if not is_valid:
        if logger and error_msg:
            logger.warning("URL validation failed: %s", error_msg)
        return False

    return True


def sanitize_input(value, max_length: int = 255) -> str:
    """Sanitize user input to reduce injection surface."""
    if not value:
        return ""

    text = str(value).strip()
    text = re.sub(r"[<>\"']", "", text)

    if len(text) > max_length:
        text = text[:max_length]

    return text


def sanitize_filename(filename: str, *, download_folder: Path, max_length: int, logger=None) -> str:
    """Limpia el nombre del archivo y valida contra path traversal."""
    cleaned = re.sub(r'[<>:"/\\|?*]', '', filename)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    if len(cleaned) > max_length:
        cleaned = cleaned[:max_length]

    if not cleaned:
        cleaned = "video_sin_titulo"

    test_path = (download_folder / cleaned).resolve()
    try:
        test_path.relative_to(download_folder.resolve())
    except ValueError:
        if logger:
            logger.warning("Path traversal attempt detected: %s", cleaned)
        raise ValueError("Invalid filename: path traversal detected")

    return cleaned
