"""Errores de dominio y manejadores HTTP.

Los servicios lanzan `AppError` con un código estable (para el frontend y una
futura app móvil) y un mensaje apto para mostrar al usuario. Cualquier otra
excepción se registra en el log y se responde con un 500 genérico, sin detalles
internos.
"""
import logging
import uuid

from flask import jsonify, request
from werkzeug.exceptions import HTTPException

log = logging.getLogger("app.errors")


class AppError(Exception):
    status = 400
    code = "bad_request"

    def __init__(self, message: str, *, code: str | None = None, status: int | None = None, details=None):
        super().__init__(message)
        self.message = message
        if code:
            self.code = code
        if status:
            self.status = status
        self.details = details


class ValidationError(AppError):
    status = 422
    code = "validation_error"


class NotFound(AppError):
    status = 404
    code = "not_found"


class Unauthorized(AppError):
    status = 401
    code = "unauthorized"


class Forbidden(AppError):
    status = 403
    code = "forbidden"


class Conflict(AppError):
    status = 409
    code = "conflict"


class TooManyRequests(AppError):
    status = 429
    code = "rate_limited"


def _payload(code, message, details=None, status=400):
    body = {"error": {"code": code, "message": message}}
    if details is not None:
        body["error"]["details"] = details
    return jsonify(body), status


def register_error_handlers(app):
    @app.errorhandler(AppError)
    def _app_error(err: AppError):
        return _payload(err.code, err.message, err.details, err.status)

    @app.errorhandler(HTTPException)
    def _http_error(err: HTTPException):
        messages = {
            404: "El recurso solicitado no existe.",
            405: "Método no permitido.",
            413: "El archivo es demasiado grande.",
            400: "La solicitud no es válida.",
        }
        if not request.path.startswith("/api/") and err.code == 404:
            from app.web.seo import render_shell
            return render_shell(status=404)
        return _payload(err.name.lower().replace(" ", "_"), messages.get(err.code, err.description), status=err.code)

    @app.errorhandler(Exception)
    def _unexpected(err: Exception):
        ref = uuid.uuid4().hex[:10]
        log.exception("Error no controlado ref=%s path=%s", ref, request.path)
        if not request.path.startswith("/api/"):
            from app.web.seo import render_shell
            return render_shell(status=500)
        return _payload("server_error", f"Ocurrió un error inesperado. Referencia: {ref}", status=500)
