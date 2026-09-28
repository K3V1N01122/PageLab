"""Protección CSRF por doble envío (cookie legible + cabecera X-CSRF-Token)
y verificación de Origin. Las peticiones con Authorization: Bearer no usan
cookies, por lo que no son vulnerables a CSRF y quedan exentas."""
from urllib.parse import urlparse

from flask import current_app, request

from app.core.errors import Forbidden
from app.core.security import constant_eq, new_token

SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


def _allowed_origins() -> set[str]:
    cfg = current_app.config
    origins = {cfg["PUBLIC_BASE_URL"], request.host_url.rstrip("/")}
    origins.update(cfg.get("CORS_ALLOWED_ORIGINS") or [])
    return {o.rstrip("/") for o in origins}


def verify_csrf() -> None:
    if request.method in SAFE_METHODS or not request.path.startswith("/api/"):
        return
    if request.headers.get("Authorization", "").startswith("Bearer "):
        return
    origin = request.headers.get("Origin")
    if origin:
        parsed = urlparse(origin)
        if f"{parsed.scheme}://{parsed.netloc}" not in _allowed_origins():
            raise Forbidden("Origen no permitido.", code="bad_origin")
    cookie = request.cookies.get(current_app.config["CSRF_COOKIE_NAME"], "")
    header = request.headers.get("X-CSRF-Token", "")
    if not cookie or not header or not constant_eq(cookie, header):
        raise Forbidden("La sesión del formulario expiró. Recarga la página e inténtalo de nuevo.", code="csrf_failed")


def ensure_csrf_cookie(response):
    name = current_app.config["CSRF_COOKIE_NAME"]
    already = any(h.startswith(f"{name}=") for h in response.headers.getlist("Set-Cookie"))
    if not request.cookies.get(name) and not already:
        response.set_cookie(
            name, new_token(24), httponly=False, samesite="Lax",
            secure=current_app.config["SESSION_COOKIE_SECURE"], path="/",
        )
    return response
