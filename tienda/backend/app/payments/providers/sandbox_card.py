"""Proveedor SOLO para desarrollo y pruebas: simula un cobro con tarjeta
aprobado. La configuración de producción rechaza habilitarlo."""
import secrets

from app.payments.base import PaymentProvider, PaymentResult


class SandboxCard(PaymentProvider):
    code = "sandbox_card"
    label = "Tarjeta (modo de prueba)"
    description = "Simula un pago aprobado. No se realiza ningún cobro real."
    online = True

    def create_payment(self, order, details=None):
        return PaymentResult(status="paid", provider_ref=f"SANDBOX-{secrets.token_hex(6).upper()}",
                             details={"simulated": True})
