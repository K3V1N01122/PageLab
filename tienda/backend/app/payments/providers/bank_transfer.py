from app.payments.base import PaymentProvider, PaymentResult
from app.services import settings_service


class BankTransfer(PaymentProvider):
    code = "bank_transfer"
    label = "Transferencia o depósito bancario"
    description = "Confirmamos tu pedido cuando recibimos el pago."

    def create_payment(self, order):
        text = settings_service.get("payments").get("bank_transfer_instructions")
        return PaymentResult(status="pending", instructions=f"{text} Referencia: {order['order_number']}.")
