"""Almacenamiento de imágenes subidas.

Backend local: guarda en UPLOAD_DIR y genera versiones WebP optimizadas
(1200 px y 400 px). Para usar S3/Cloudinary en producción, implemente otra
clase con el mismo método `save_image` y selecciónela aquí.
"""
from __future__ import annotations

import io
import secrets
from datetime import datetime, timezone

from flask import current_app

from app.core.errors import ValidationError

ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP", "GIF"}
SIZES = {"lg": 1200, "sm": 400}


def save_image(file_storage) -> dict:
    try:
        from PIL import Image, ImageOps
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("Pillow es necesario para subir imágenes") from exc
    data = file_storage.read()
    if not data:
        raise ValidationError("El archivo está vacío.")
    try:
        img = Image.open(io.BytesIO(data))
        img.verify()  # valida que sea realmente una imagen (no confía en la extensión)
        img = Image.open(io.BytesIO(data))
    except Exception:
        raise ValidationError("El archivo no es una imagen válida.")
    if img.format not in ALLOWED_FORMATS:
        raise ValidationError("Formato no permitido. Usa JPG, PNG, WebP o GIF.")
    if img.width * img.height > 40_000_000:
        raise ValidationError("La imagen es demasiado grande.")
    img = ImageOps.exif_transpose(img).convert("RGBA" if img.mode in ("RGBA", "LA", "P") else "RGB")
    folder = datetime.now(timezone.utc).strftime("%Y/%m")
    target = current_app.config["UPLOAD_DIR"] / folder
    target.mkdir(parents=True, exist_ok=True)
    name = secrets.token_hex(10)
    urls = {}
    for key, max_side in SIZES.items():
        copy = img.copy()
        copy.thumbnail((max_side, max_side))
        path = target / f"{name}-{key}.webp"
        copy.save(path, "WEBP", quality=82, method=6)
        urls[key] = f"{current_app.config['UPLOAD_URL_PREFIX']}/{folder}/{path.name}"
    return {"url": urls["lg"], "thumb_url": urls["sm"], "width": img.width, "height": img.height}
