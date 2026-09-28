import uuid

from app.core.timeutil import now_iso
from tests.helpers import BaseTest


class LoyaltyTests(BaseTest):
    def setUp(self):
        super().setUp()
        self.c = self.client()
        self.email = self.c.register()
        self.reward_id = self.db.insert(
            """INSERT INTO rewards (name, kind, points_cost, value_cents, is_active, created_at, updated_at)
               VALUES ('Q50', 'fixed_discount', 1000, 5000, TRUE, ?, ?)""", (now_iso(), now_iso()))

    def redeem(self, key=None, reward_id=None):
        return self.c.post(f"/api/v1/rewards/{reward_id or self.reward_id}/redeem", {"idempotency_key": key or uuid.uuid4().hex})

    def test_redeem_generates_personal_coupon_and_movement(self):
        self.give_points(self.email, 1200)
        r = self.redeem()
        self.assertEqual(r.status_code, 201, r.get_json())
        data = r.get_json()
        self.assertTrue(data["coupon_code"].startswith("R-"))
        self.assertEqual(data["points_available"], 200)
        movements = self.c.get("/api/v1/loyalty/movements").get_json()["items"]
        self.assertEqual(movements[0]["kind"], "redeem")
        self.assertEqual(movements[0]["points"], -1000)
        # El cupón funciona en el carrito y solo para su dueño
        pid = self.make_product(price=20000)
        self.c.post("/api/v1/cart/items", {"product_id": pid})
        q = self.c.post("/api/v1/cart/preview", {"coupon_code": data["coupon_code"]}).get_json()
        self.assertEqual(q["discount_cents"], 5000)
        other = self.client()
        other.register()
        other.post("/api/v1/cart/items", {"product_id": pid})
        q = other.post("/api/v1/cart/preview", {"coupon_code": data["coupon_code"]}).get_json()
        self.assertEqual(q["discount_cents"], 0)

    def test_insufficient_points(self):
        self.give_points(self.email, 999)
        r = self.redeem()
        self.assertEqual(r.status_code, 409)
        self.assertEqual(r.get_json()["error"]["code"], "insufficient_points")
        self.assertEqual(self.db.scalar("SELECT COUNT(*) AS n FROM coupons"), 0)
        self.assertEqual(self.db.scalar("SELECT COUNT(*) AS n FROM reward_redemptions"), 0)

    def test_idempotent_redeem(self):
        self.give_points(self.email, 5000)
        key = uuid.uuid4().hex
        a = self.redeem(key).get_json()
        b = self.redeem(key).get_json()
        self.assertEqual(a["redemption_id"], b["redemption_id"])
        self.assertEqual(self.c.get("/api/v1/loyalty/card").get_json()["points_available"], 4000)

    def test_reward_stock_and_inactive(self):
        self.give_points(self.email, 5000)
        self.db.execute("UPDATE rewards SET stock = 1 WHERE id = ?", (self.reward_id,))
        self.assertEqual(self.redeem().status_code, 201)
        self.assertEqual(self.redeem().status_code, 409)
        self.db.execute("UPDATE rewards SET stock = NULL, is_active = FALSE WHERE id = ?", (self.reward_id,))
        self.assertEqual(self.redeem().status_code, 409)

    def test_per_user_limit(self):
        self.give_points(self.email, 5000)
        self.db.execute("UPDATE rewards SET per_user_limit = 1 WHERE id = ?", (self.reward_id,))
        self.assertEqual(self.redeem().status_code, 201)
        self.assertEqual(self.redeem().get_json()["error"]["code"], "reward_limit")

    def test_points_cannot_be_set_from_frontend(self):
        r = self.c.put("/api/v1/account/profile", {"first_name": "A", "last_name": "B", "points_balance": 999999})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.c.get("/api/v1/loyalty/card").get_json()["points_available"], 0)

    def test_admin_adjust_and_configurable_rate(self):
        admin = self.make_admin()
        uid = self.user_id(self.email)
        r = admin.post(f"/api/v1/admin/users/{uid}/points", {"points": 700, "reason": "Compensación"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(admin.post(f"/api/v1/admin/users/{uid}/points", {"points": -800, "reason": "Error"}).status_code, 409)
        r = admin.put("/api/v1/admin/loyalty/settings", {"points_per_currency_unit": 2, "redeem_block_points": 500,
                                                         "redeem_block_value_cents": 2500})
        self.assertEqual(r.status_code, 200)
        pid = self.make_product(price=10000)
        self.c.post("/api/v1/cart/items", {"product_id": pid})
        q = self.c.post("/api/v1/cart/preview", {"points_to_use": 500}).get_json()
        self.assertEqual(q["points_discount_cents"], 2500)
        self.assertEqual(q["points_earned"], 150)  # (Q100 - Q25) * 2

    def test_invalid_loyalty_settings_rejected(self):
        admin = self.make_admin()
        r = admin.put("/api/v1/admin/loyalty/settings", {"redeem_block_points": 0})
        self.assertEqual(r.status_code, 422)
        r = admin.put("/api/v1/admin/loyalty/settings", {"points_per_currency_unit": -1})
        self.assertEqual(r.status_code, 422)
