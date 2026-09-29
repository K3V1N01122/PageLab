import json
from datetime import datetime

from tests.helpers import BaseTest

FUTURE = datetime.now().year + 2


def card(last4="4242", brand="visa", **extra):
    return {"brand": brand, "last4": last4, "exp_month": 12, "exp_year": FUTURE, "holder": "Ana Prueba", **extra}


class CardDemoTests(BaseTest):
    def setUp(self):
        super().setUp()
        self.c = self.client()
        self.c.register()
        self.pid = self.make_product(price=25000, stock=3)
        self.c.post("/api/v1/cart/items", {"product_id": self.pid})

    def test_approved_card_marks_order_paid(self):
        r = self.checkout(self.c, payment_provider="card_demo", payment_details=card())
        self.assertEqual(r.status_code, 201, r.get_json())
        order = r.get_json()
        self.assertEqual(order["status"], "paid")
        self.assertEqual(order["payment"]["card"], {"brand": "Visa", "last4": "4242", "demo": True})

    def test_mastercard_accepted(self):
        r = self.checkout(self.c, payment_provider="card_demo", payment_details=card("4444", "mastercard"))
        self.assertEqual(r.get_json()["payment"]["card"]["brand"], "Mastercard")

    def test_declined_card_creates_no_order_and_keeps_stock(self):
        r = self.checkout(self.c, payment_provider="card_demo", payment_details=card("0002"))
        self.assertEqual(r.status_code, 402)
        self.assertEqual(r.get_json()["error"]["code"], "payment_declined")
        self.assertEqual(self.db.scalar("SELECT COUNT(*) AS n FROM orders"), 0)
        self.assertEqual(self.db.scalar("SELECT stock FROM products WHERE id = ?", (self.pid,)), 3)
        self.assertEqual(len(self.c.get("/api/v1/cart").get_json()["lines"]), 1)  # el carrito sigue intacto

    def test_invalid_card_details(self):
        for bad in (card(brand="amex"), card(last4="12"), {**card(), "exp_year": 2001}, {**card(), "holder": ""}, None):
            r = self.checkout(self.c, payment_provider="card_demo", payment_details=bad)
            self.assertEqual(r.status_code, 422, bad)

    def test_full_card_number_and_cvv_are_never_stored(self):
        self.checkout(self.c, payment_provider="card_demo",
                      payment_details=card(number="4242424242424242", cvv="123"))
        stored = json.dumps(self.db.all("SELECT * FROM payments")) + json.dumps(self.db.all("SELECT * FROM orders"))
        self.assertNotIn("4242424242424242", stored)
        self.assertNotIn('"123"', stored)

    def test_card_demo_blocked_in_production_without_demo_mode(self):
        from app.config import ProductionConfig
        saved = (ProductionConfig.SECRET_KEY, ProductionConfig.DATABASE_URL, ProductionConfig.PAYMENT_PROVIDERS, ProductionConfig.DEMO_MODE)
        try:
            ProductionConfig.SECRET_KEY = "x" * 40
            ProductionConfig.DATABASE_URL = "postgresql://u:p@h/db"
            ProductionConfig.PAYMENT_PROVIDERS = ["card_demo"]
            ProductionConfig.DEMO_MODE = False
            with self.assertRaises(RuntimeError):
                ProductionConfig.validate()
            ProductionConfig.DEMO_MODE = True
            ProductionConfig.validate()
        finally:
            (ProductionConfig.SECRET_KEY, ProductionConfig.DATABASE_URL, ProductionConfig.PAYMENT_PROVIDERS, ProductionConfig.DEMO_MODE) = saved
