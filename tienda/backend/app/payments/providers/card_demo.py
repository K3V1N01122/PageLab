"""Tarjeta Visa / Mastercard en MODO DEMOSTRACIÓN.

Muestra el flujo completo de pago con tarjeta sin cobrar nada. Sirve para
enseñar la tienda a clientes mientras se elige una pasarela real.

Seguridad (igual que con una pasarela real):
- El número completo y el CVV NUNCA llegan al servidor: el navegador valida
  la tarjeta y solo envía la marca, los últimos 4 dígitos, el vencimiento y
  el nombre del titular.
- En producción solo se puede habilitar con DEMO_MODE=true (config.py).

Tarjetas de prueba: terminada en 0002 = rechazada por fondos insuficientes;
cualquier otra Visa/Mastercard válida = aprobada.
"""
import re
import secrets
from datetime import datetime, timezone

from app.core.errors import ValidationError
from app.payments.base import PaymentProvider, PaymentResult

BRANDS = {"visa": "Visa", "mastercard": "Mastercard"}
DECLINED_LAST4 = {"0002": "La tarjeta fue rechazada por fondos insuficientes. Prueba con otra tarjeta."}


class CardDemo(PaymentProvider):
    code = "card_demo"
    label = "Tarjeta de crédito o débito"
    description = "Visa o Mastercard. Modo demostración: no se realiza ningún cobro."
    online = True
    form = "card"
    demo = True

    def validate_details(self, details) -> dict:
        d = details if isinstance(details, dict) else {}
        errors = {}
        brand = d.get("brand")
        if brand not in BRANDS:
            errors["card.number"] = "Solo aceptamos Visa o Mastercard."
        last4 = str(d.get("last4") or "")
        if not re.fullmatch(r"\d{4}", last4):
            errors["card.number"] = errors.get("card.number") or "Número de tarjeta no válido."
        try:
            month, year = int(d.get("exp_month")), int(d.get("exp_year"))
            now = datetime.now(timezone.utc)
            if not 1 <= month <= 12 or (year, month) < (now.year, now.month) or year > now.year + 20:
                raise ValueError
        except (TypeError, ValueError):
            errors["card.exp"] = "La fecha de vencimiento no es válida."
        holder = (d.get("holder") or "").strip()
        if not 3 <= len(holder) <= 80:
            errors["card.holder"] = "Escribe el nombre como aparece en la tarjeta."
        if errors:
            raise ValidationError("Revisa los datos de la tarjeta.", details=errors)
        # Solo se conservan datos no sensibles; cualquier otro campo se descarta.
        return {"brand": brand, "last4": last4, "exp_month": month, "exp_year": year, "holder": holder[:80]}

    def create_payment(self, order, details=None):
        d = details or {}
        card = {"brand": BRANDS.get(d.get("brand"), ""), "last4": d.get("last4"), "demo": True}
        if d.get("last4") in DECLINED_LAST4:
            return PaymentResult(status="failed", message=DECLINED_LAST4[d["last4"]], details={"card": card})
        return PaymentResult(status="paid", provider_ref=f"DEMO-{secrets.token_hex(5).upper()}", details={"card": card})
