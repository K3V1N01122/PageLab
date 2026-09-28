import uuid

from app.core.timeutil import now_iso
from tests.helpers import BaseTest


class CheckoutTests(BaseTest):
    def setUp(self):
        super().setUp()
        self.c = self.client()
        self.email = self.c.register()
        self.uid = self.user_id(self.email)

    def _order_ready(self, price=10000, stock=5, qty=1):
        pid = self.make_product(price=price, stock=stock)
        self.c.post("/api/v1/cart/items", {"product_id": pid, "quantity": qty})
        return pid

    def test_checkout_creates_order_and_decrements_stock(self):
        pid = self._order_ready(stock=5, qty=2)
        r = self.checkout(self.c)
        self.assertEqual(r.status_code, 201, r.get_json())
        order = r.get_json()
        self.assertRegex(order["order_number"], r"^PD-\d{6}-[A-Z2-9]{5}$")
        self.assertEqual(order["status"], "pending")
        self.assertEqual(order["total_cents"], 20000)
        self.assertEqual(self.db.scalar("SELECT stock FROM products WHERE id = ?", (pid,)), 3)
        self.assertEqual(self.c.get("/api/v1/cart").get_json()["lines"], [])
        self.assertEqual(order["points_earned"], 200)
        card = self.c.get("/api/v1/loyalty/card").get_json()
        self.assertEqual(card["points_pending"], 200)
        self.assertEqual(card["points_available"], 0)

    def test_idempotent_checkout(self):
        self._order_ready()
        key = uuid.uuid4().hex
        a = self.checkout(self.c, idempotency_key=key).get_json()
        b = self.checkout(self.c, idempotency_key=key).get_json()
        self.assertEqual(a["order_number"], b["order_number"])
        self.assertEqual(self.db.scalar("SELECT COUNT(*) AS n FROM orders"), 1)

    def test_expected_total_mismatch_returns_409(self):
        pid = self._order_ready(price=10000)
        self.db.execute("UPDATE products SET price_cents = 15000 WHERE id = ?", (pid,))
        r = self.checkout(self.c, expected_total_cents=10000)
        self.assertEqual(r.status_code, 409)
        self.assertEqual(r.get_json()["error"]["code"], "price_changed")
        self.assertEqual(r.get_json()["error"]["details"]["total_cents"], 15000)
        self.assertEqual(self.db.scalar("SELECT COUNT(*) AS n FROM orders"), 0)

    def test_manipulated_total_is_ignored(self):
        self._order_ready(price=10000)
        order = self.checkout(self.c, total_cents=1, discount_cents=99999, points_earned=10**6).get_json()
        self.assertEqual(order["total_cents"], 10000)
        self.assertEqual(order["points_earned"], 100)

    def test_address_required_for_delivery(self):
        self._order_ready()
        r = self.checkout(self.c, shipping_method="standard")
        self.assertEqual(r.status_code, 422)
        r = self.checkout(self.c, shipping_method="standard", address={
            "recipient": "Ana", "phone": "55555555", "line1": "6a avenida 1-23", "city": "Guatemala"})
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.get_json()["shipping_cents"], 3000)
        self.assertEqual(r.get_json()["shipping_address"]["city"], "Guatemala")

    def test_empty_cart_and_invalid_payment(self):
        r = self.checkout(self.c)
        self.assertEqual(r.get_json()["error"]["code"], "cart_empty")
        self._order_ready()
        r = self.checkout(self.c, payment_provider="bitcoin_magico")
        self.assertEqual(r.status_code, 422)

    def test_points_spent_and_refunded_on_cancel(self):
        pid = self._order_ready(price=40000, stock=3)
        self.give_points(self.email, 2500)
        order = self.checkout(self.c, points_to_use=2000).get_json()
        self.assertEqual(order["points_used"], 2000)
        self.assertEqual(order["points_discount_cents"], 10000)
        self.assertEqual(order["total_cents"], 30000)
        self.assertEqual(self.c.get("/api/v1/loyalty/card").get_json()["points_available"], 500)
        r = self.c.post(f"/api/v1/account/orders/{order['order_number']}/cancel")
        self.assertEqual(r.status_code, 200)
        card = self.c.get("/api/v1/loyalty/card").get_json()
        self.assertEqual(card["points_available"], 2500)
        self.assertEqual(card["points_pending"], 0)
        self.assertEqual(self.db.scalar("SELECT stock FROM products WHERE id = ?", (pid,)), 3)

    def test_coupon_usage_limits(self):
        self.db.insert("""INSERT INTO coupons (code, kind, value_cents, max_uses, per_user_limit, is_active, created_at, updated_at)
                          VALUES ('UNA', 'fixed', 1000, 1, 1, TRUE, ?, ?)""", (now_iso(), now_iso()))
        self._order_ready()
        self.assertEqual(self.checkout(self.c, coupon_code="UNA").status_code, 201)
        self._order_ready()
        r = self.checkout(self.c, coupon_code="UNA")
        self.assertEqual(r.status_code, 422)
        self.assertEqual(r.get_json()["error"]["code"], "coupon_invalid")

    def test_points_posted_when_delivered(self):
        self._order_ready(price=25000)
        order = self.checkout(self.c).get_json()
        admin = self.make_admin()
        for status in ("preparing", "shipped", "delivered"):
            r = admin.post(f"/api/v1/admin/orders/{order['id']}/status", {"status": status})
            self.assertEqual(r.status_code, 200, r.get_json())
        card = self.c.get("/api/v1/loyalty/card").get_json()
        self.assertEqual(card["points_available"], 250)
        self.assertEqual(card["points_pending"], 0)
        detail = self.c.get(f"/api/v1/account/orders/{order['order_number']}").get_json()
        self.assertEqual(detail["payment_status"], "paid")
        self.assertEqual([h["to_status"] for h in detail["history"]], ["pending", "preparing", "shipped", "delivered"])

    def test_invalid_transition(self):
        self._order_ready()
        order = self.checkout(self.c).get_json()
        admin = self.make_admin()
        r = admin.post(f"/api/v1/admin/orders/{order['id']}/status", {"status": "delivered"})
        self.assertEqual(r.status_code, 422)

    def test_customer_cannot_cancel_processing_order(self):
        self._order_ready()
        order = self.checkout(self.c).get_json()
        admin = self.make_admin()
        admin.post(f"/api/v1/admin/orders/{order['id']}/status", {"status": "preparing"})
        r = self.c.post(f"/api/v1/account/orders/{order['order_number']}/cancel")
        self.assertEqual(r.status_code, 409)

    def test_sandbox_payment_marks_paid(self):
        self._order_ready()
        order = self.checkout(self.c, payment_provider="sandbox_card").get_json()
        self.assertEqual(order["status"], "paid")
        self.assertEqual(order["payment_status"], "paid")

    def test_user_cannot_see_other_users_orders(self):
        self._order_ready()
        order = self.checkout(self.c).get_json()
        other = self.client()
        other.register()
        self.assertEqual(other.get(f"/api/v1/account/orders/{order['order_number']}").status_code, 404)

    def test_order_confirmation_email(self):
        from app.services.notification_service import MemoryMailer
        self._order_ready()
        order = self.checkout(self.c).get_json()
        self.assertTrue(any(order["order_number"] in m["subject"] for m in MemoryMailer.outbox))
