from app.payments.base import PaymentProvider, PaymentResult


class CashOnDelivery(PaymentProvider):
    code = "cash_on_delivery"
    label = "Pago contra entrega"
    description = "Pagas en efectivo o con tarjeta al recibir tu pedido."

    def create_payment(self, order, details=None):
        return PaymentResult(status="pending", instructions="Paga al recibir tu pedido.")
