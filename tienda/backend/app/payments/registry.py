from flask import current_app

from app.core.errors import ValidationError
from app.payments.providers.bank_transfer import BankTransfer
from app.payments.providers.cash_on_delivery import CashOnDelivery
from app.payments.providers.sandbox_card import SandboxCard

PROVIDERS = {cls.code: cls for cls in (CashOnDelivery, BankTransfer, SandboxCard)}


def enabled() -> list:
    return [PROVIDERS[c]() for c in current_app.config["PAYMENT_PROVIDERS"] if c in PROVIDERS]


def get(code: str):
    if code not in current_app.config["PAYMENT_PROVIDERS"] or code not in PROVIDERS:
        raise ValidationError("Selecciona un método de pago válido.", details={"payment_provider": "No disponible."})
    return PROVIDERS[code]()
