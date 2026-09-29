"""Interfaz común para proveedores de pago.

Para integrar un proveedor nuevo (Stripe, PayPal, una pasarela local...):
1. Cree `providers/<codigo>.py` con una subclase de PaymentProvider.
2. Regístrela en `registry.PROVIDERS`.
3. Habilítela con la variable de entorno PAYMENT_PROVIDERS.
Las claves del proveedor se leen de variables de entorno, nunca del frontend.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class PaymentResult:
    status: str                      # pending | authorized | paid | failed
    message: str | None = None       # motivo para el cliente si se rechaza
    provider_ref: str | None = None
    instructions: str | None = None  # texto para el cliente (p. ej. transferencia)
    redirect_url: str | None = None  # para pasarelas con página externa
    details: dict = field(default_factory=dict)


class PaymentProvider:
    code: str = ""
    label: str = ""
    description: str = ""
    online: bool = False             # True si el cobro ocurre en línea
    form: str | None = None          # formulario que muestra el checkout (p. ej. "card")
    demo: bool = False               # True si no realiza cobros reales

    def validate_details(self, details) -> dict:
        """Valida los datos extra que envía el checkout (p. ej. marca y últimos
        4 dígitos de la tarjeta). Por defecto el método no necesita datos."""
        return {}

    def create_payment(self, order: dict, details: dict | None = None) -> PaymentResult:
        raise NotImplementedError

    def handle_webhook(self, payload: bytes, headers: dict) -> dict | None:
        """Verifica la firma del proveedor y devuelve {"provider_ref", "status"}.
        Los proveedores sin webhooks devuelven None."""
        return None

    def public_info(self) -> dict:
        return {"code": self.code, "label": self.label, "description": self.description, "online": self.online,
                "form": self.form, "demo": self.demo}
