"""Configuración por entorno.

Todos los valores sensibles o que cambian entre entornos se leen de variables
de entorno. Los valores de negocio que el administrador puede cambiar (puntos,
envíos, redes sociales...) viven en la tabla `settings` y se editan desde el
panel; aquí solo están sus valores iniciales.
"""
from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent  # backend/
PROJECT_DIR = BASE_DIR.parent


def _bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


def _list(name: str, default: str = "") -> list[str]:
    return [v.strip() for v in os.getenv(name, default).split(",") if v.strip()]


class BaseConfig:
    ENV = "development"
    DEBUG = False
    TESTING = False

    SECRET_KEY = os.getenv("SECRET_KEY", "")
    DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'instance' / 'dev.sqlite3'}")

    # URLs públicas (SEO, correos, CORS)
    PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "http://localhost:5000").rstrip("/")
    CORS_ALLOWED_ORIGINS = _list("CORS_ALLOWED_ORIGINS")

    # Frontend estático (en producción lo sirve nginx; en desarrollo, Flask)
    FRONTEND_DIR = Path(os.getenv("FRONTEND_DIR", PROJECT_DIR / "frontend"))
    SERVE_FRONTEND = _bool("SERVE_FRONTEND", True)

    # Archivos subidos
    UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", BASE_DIR / "instance" / "uploads"))
    UPLOAD_URL_PREFIX = os.getenv("UPLOAD_URL_PREFIX", "/uploads")
    MAX_CONTENT_LENGTH = _int("MAX_UPLOAD_MB", 8) * 1024 * 1024

    # Sesiones
    SESSION_COOKIE_NAME = "sid"
    CSRF_COOKIE_NAME = "csrf_token"
    SESSION_COOKIE_SECURE = _bool("SESSION_COOKIE_SECURE", False)
    SESSION_HOURS = _int("SESSION_HOURS", 12)
    SESSION_REMEMBER_DAYS = _int("SESSION_REMEMBER_DAYS", 30)

    # Fuerza bruta
    LOGIN_MAX_FAILURES = _int("LOGIN_MAX_FAILURES", 5)
    LOGIN_LOCK_MINUTES = _int("LOGIN_LOCK_MINUTES", 15)

    # Rate limiting (peticiones por ventana)
    RATE_LIMIT_ENABLED = _bool("RATE_LIMIT_ENABLED", True)
    RATE_LIMIT_DEFAULT = os.getenv("RATE_LIMIT_DEFAULT", "300/60")  # 300 por minuto por IP
    RATE_LIMIT_AUTH = os.getenv("RATE_LIMIT_AUTH", "10/60")
    RATE_LIMIT_CHECKOUT = os.getenv("RATE_LIMIT_CHECKOUT", "20/60")
    TRUST_PROXY_HEADERS = _bool("TRUST_PROXY_HEADERS", False)

    # Pagos: proveedores habilitados, en orden de aparición en el checkout
    PAYMENT_PROVIDERS = _list("PAYMENT_PROVIDERS", "cash_on_delivery,bank_transfer")
    # Modo demostración: permite el pago con tarjeta simulado (card_demo) en una
    # tienda publicada. Nunca activarlo en la tienda real de un cliente.
    DEMO_MODE = _bool("DEMO_MODE", False)

    # Correo (proveedor pendiente de definir: por defecto se registra en el log)
    MAIL_BACKEND = os.getenv("MAIL_BACKEND", "console")
    BREVO_API_KEY = os.getenv("BREVO_API_KEY", "")
    MAIL_FROM = os.getenv("MAIL_FROM", "")            # vacío = se usa SMTP_USER
    MAIL_FROM_NAME = os.getenv("MAIL_FROM_NAME", "")  # vacío = nombre de la tienda
    SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
    SMTP_PORT = _int("SMTP_PORT", 587)
    SMTP_USER = os.getenv("SMTP_USER", "")
    SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")

    AUTO_MIGRATE = _bool("AUTO_MIGRATE", False)
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    CACHE_PUBLIC_SECONDS = _int("CACHE_PUBLIC_SECONDS", 60)


class DevelopmentConfig(BaseConfig):
    ENV = "development"
    DEBUG = True
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-only-insecure-key-change-me")
    PAYMENT_PROVIDERS = _list("PAYMENT_PROVIDERS", "cash_on_delivery,bank_transfer,card_demo")


class TestingConfig(BaseConfig):
    ENV = "testing"
    TESTING = True
    SECRET_KEY = "testing-key"
    DATABASE_URL = os.getenv("TEST_DATABASE_URL", "sqlite:///:memory:")
    RATE_LIMIT_ENABLED = False
    PAYMENT_PROVIDERS = ["cash_on_delivery", "bank_transfer", "card_demo", "sandbox_card"]
    SERVE_FRONTEND = False
    LOG_LEVEL = "WARNING"


class ProductionConfig(BaseConfig):
    ENV = "production"
    SESSION_COOKIE_SECURE = _bool("SESSION_COOKIE_SECURE", True)
    SERVE_FRONTEND = _bool("SERVE_FRONTEND", False)
    TRUST_PROXY_HEADERS = _bool("TRUST_PROXY_HEADERS", True)

    @classmethod
    def validate(cls) -> None:
        if not cls.SECRET_KEY or len(cls.SECRET_KEY) < 32:
            raise RuntimeError("SECRET_KEY debe definirse en producción (mínimo 32 caracteres).")
        if cls.DATABASE_URL.startswith("sqlite"):
            raise RuntimeError("En producción use PostgreSQL (DATABASE_URL=postgresql://...).")
        if "sandbox_card" in cls.PAYMENT_PROVIDERS:
            raise RuntimeError("El proveedor sandbox_card no puede habilitarse en producción.")
        if "card_demo" in cls.PAYMENT_PROVIDERS and not cls.DEMO_MODE:
            raise RuntimeError("card_demo (tarjeta de demostración) solo se permite con DEMO_MODE=true.")


CONFIGS = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
}


def get_config(name: str | None = None):
    name = name or os.getenv("APP_ENV", "development")
    if name not in CONFIGS:
        raise RuntimeError(f"APP_ENV desconocido: {name}")
    return CONFIGS[name]
