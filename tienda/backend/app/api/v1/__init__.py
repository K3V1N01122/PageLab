"""API REST v1. Versionada para que una app móvil o integraciones externas
puedan convivir con cambios futuros (v2) sin romperse."""
from flask import Blueprint

api_v1 = Blueprint("api_v1", __name__, url_prefix="/api/v1")

from app.api.v1 import account, auth, cart, catalog, checkout, loyalty, public  # noqa: E402,F401
from app.api.v1.admin import register as register_admin  # noqa: E402

register_admin(api_v1)
