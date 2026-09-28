"""Configuración de la tienda editable desde el panel (tabla `settings`).

Se cachea en memoria unos segundos para no consultar la BD en cada request.
Con varias instancias, un cambio tarda como máximo CACHE_TTL en verse en todas.
"""
import copy
import json
import threading
import time

from app.core.errors import ValidationError
from app.core.jsonutil import load_json
from app.core.timeutil import now_iso
from app.db import get_db
from app.db.migrate import DEFAULT_SETTINGS

CACHE_TTL = 30
_cache: dict = {"at": 0.0, "data": None}
_lock = threading.Lock()


def all_settings() -> dict:
    with _lock:
        if _cache["data"] is not None and time.time() - _cache["at"] < CACHE_TTL:
            return copy.deepcopy(_cache["data"])
    rows = get_db().all("SELECT key, value FROM settings")
    data = copy.deepcopy(DEFAULT_SETTINGS)
    for row in rows:
        value = load_json(row["value"], {})
        if isinstance(value, dict) and isinstance(data.get(row["key"]), dict):
            data[row["key"]].update(value)
        else:
            data[row["key"]] = value
    with _lock:
        _cache.update(at=time.time(), data=data)
    return copy.deepcopy(data)


def get(key: str) -> dict:
    return all_settings().get(key, {})


def invalidate() -> None:
    with _lock:
        _cache.update(at=0.0, data=None)


# Validadores por sección: evitan guardar configuraciones que rompan la tienda.
def _validate_loyalty(v: dict) -> dict:
    ints = ["points_per_currency_unit", "redeem_block_points", "redeem_block_value_cents", "max_points_discount_percent"]
    for k in ints:
        if k in v and (not isinstance(v[k], int) or isinstance(v[k], bool) or v[k] < 0):
            raise ValidationError("Valores de puntos no válidos.", details={k: "Debe ser un entero positivo."})
    if v.get("redeem_block_points") == 0:
        raise ValidationError("Valores de puntos no válidos.", details={"redeem_block_points": "Debe ser mayor que 0."})
    if v.get("max_points_discount_percent", 0) > 100:
        raise ValidationError("Valores de puntos no válidos.", details={"max_points_discount_percent": "Máximo 100."})
    if "earn_on_status" in v and v["earn_on_status"] not in {"paid", "delivered"}:
        raise ValidationError("Valores de puntos no válidos.", details={"earn_on_status": "Use paid o delivered."})
    return v


def _validate_shipping(v: dict) -> dict:
    methods = v.get("methods", [])
    if not isinstance(methods, list) or not methods:
        raise ValidationError("Configura al menos un método de entrega.")
    codes = set()
    for m in methods:
        if not isinstance(m, dict) or not m.get("code") or not m.get("label"):
            raise ValidationError("Cada método necesita código y nombre.")
        if not isinstance(m.get("price_cents", 0), int) or m.get("price_cents", 0) < 0:
            raise ValidationError("El precio de envío no es válido.")
        if m["code"] in codes:
            raise ValidationError("Hay códigos de envío repetidos.")
        codes.add(m["code"])
    return v


def _safe_url(value, field, allow_relative=False):
    """Evita enlaces peligrosos (javascript:, data:) en datos que se pintan como href/src."""
    if value in (None, ""):
        return None
    if not isinstance(value, str) or len(value) > 500:
        raise ValidationError("Enlace no válido.", details={field: "Enlace no válido."})
    if value.startswith("https://") or value.startswith("http://") or (allow_relative and value.startswith("/") and not value.startswith("//")):
        return value
    raise ValidationError("Usa un enlace que empiece con https://", details={field: "Debe empezar con https://"})


def _validate_social(v: dict) -> dict:
    for k in ("facebook", "instagram", "tiktok"):
        v[k] = _safe_url(v.get(k), k)
    return v


def _validate_store(v: dict) -> dict:
    if not (v.get("name") or "").strip():
        raise ValidationError("El nombre es obligatorio.", details={"name": "Obligatorio."})
    v["logo_url"] = _safe_url(v.get("logo_url"), "logo_url", allow_relative=True)
    for field, limit in (("tagline", 160), ("statement", 400), ("closing_line", 60)):
        value = v.get(field)
        if value is not None and (not isinstance(value, str) or len(value) > limit):
            raise ValidationError("Texto demasiado largo.", details={field: f"Máximo {limit} caracteres."})
    v["is_placeholder"] = False
    return v


FONT_PRESETS = {"deportiva", "editorial", "urbana", "clasica"}


def _validate_theme(v: dict) -> dict:
    import re
    if v.get("font") and v["font"] not in FONT_PRESETS:
        raise ValidationError("Tipografía no válida.", details={"font": "Elige una opción de la lista."})
    for k in ("primary", "accent", "points"):
        if v.get(k) and not re.fullmatch(r"#[0-9a-fA-F]{6}", v[k]):
            raise ValidationError("Color no válido.", details={k: "Usa formato #RRGGBB."})
    return v


def _validate_contact(v: dict) -> dict:
    for k in ("email", "phone", "whatsapp", "address", "hours"):
        if v.get(k) is not None and (not isinstance(v[k], str) or len(v[k]) > 200):
            raise ValidationError("Dato de contacto no válido.", details={k: "Máximo 200 caracteres."})
    return v


def _validate_seo(v: dict) -> dict:
    v["og_image"] = _safe_url(v.get("og_image"), "og_image", allow_relative=True)
    return v


VALIDATORS = {"loyalty": _validate_loyalty, "shipping": _validate_shipping, "social": _validate_social,
              "store": _validate_store, "theme": _validate_theme, "contact": _validate_contact, "seo": _validate_seo}
EDITABLE = set(DEFAULT_SETTINGS)


def update(key: str, value: dict) -> dict:
    if key not in EDITABLE:
        raise ValidationError("Sección de configuración desconocida.")
    if not isinstance(value, dict):
        raise ValidationError("La configuración debe ser un objeto.")
    current = get(key)
    current.update(value)
    if key in VALIDATORS:
        current = VALIDATORS[key](current)
    db = get_db()
    with db.transaction():
        updated = db.execute("UPDATE settings SET value = ?, updated_at = ? WHERE key = ?",
                             (json.dumps(current), now_iso(), key))
        if not updated:
            db.execute("INSERT INTO settings (key, value, updated_at) VALUES (?, ?, ?)",
                       (key, json.dumps(current), now_iso()))
    invalidate()
    return current
