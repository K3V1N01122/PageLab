from app.core.timeutil import now_iso
from tests.helpers import BaseTest


class CartPricingTests(BaseTest):
    def setUp(self):
        super().setUp()
        self.c = self.client()
        self.email = self.c.register()

    def test_add_update_remove(self):
        pid = self.make_product(price=2500, stock=10)
        r = self.c.post("/api/v1/cart/items", {"product_id": pid, "quantity": 2})
        self.assertEqual(r.status_code, 201)
        cart = r.get_json()
        self.assertEqual(cart["subtotal_cents"], 5000)
        cart = self.c.put(f"/api/v1/cart/items/{pid}", {"quantity": 3}).get_json()
        self.assertEqual(cart["subtotal_cents"], 7500)
        cart = self.c.delete(f"/api/v1/cart/items/{pid}").get_json()
        self.assertEqual(cart["lines"], [])

    def test_client_cannot_send_prices(self):
        pid = self.make_product(price=10000)
        cart = self.c.post("/api/v1/cart/items", {"product_id": pid, "quantity": 1, "price_cents": 1, "unit_price_cents": 1}).get_json()
        self.assertEqual(cart["total_cents"], 10000)

    def test_cannot_exceed_stock(self):
        pid = self.make_product(stock=2)
        r = self.c.post("/api/v1/cart/items", {"product_id": pid, "quantity": 3})
        self.assertEqual(r.status_code, 422)
        self.assertEqual(r.get_json()["error"]["code"], "insufficient_stock")

    def test_inactive_or_out_of_stock_products(self):
        draft = self.make_product(status="draft")
        self.assertEqual(self.c.post("/api/v1/cart/items", {"product_id": draft}).status_code, 404)
        empty = self.make_product(stock=0)
        self.assertEqual(self.c.post("/api/v1/cart/items", {"product_id": empty}).status_code, 422)

    def test_out_of_stock_after_adding_blocks_checkout(self):
        pid = self.make_product(stock=5)
        self.c.post("/api/v1/cart/items", {"product_id": pid, "quantity": 2})
        self.db.execute("UPDATE products SET stock = 0 WHERE id = ?", (pid,))
        cart = self.c.get("/api/v1/cart").get_json()
        self.assertFalse(cart["can_checkout"])
        self.assertEqual(cart["issues"][0]["code"], "out_of_stock")

    def test_price_change_is_reported_once(self):
        pid = self.make_product(price=10000)
        self.c.post("/api/v1/cart/items", {"product_id": pid})
        self.db.execute("UPDATE products SET price_cents = 12000 WHERE id = ?", (pid,))
        cart = self.c.get("/api/v1/cart").get_json()
        self.assertEqual(cart["price_changes"], [pid])
        self.assertEqual(cart["lines"][0]["previous_unit_price_cents"], 10000)
        self.assertEqual(cart["total_cents"], 12000)
        self.assertEqual(self.c.get("/api/v1/cart").get_json()["price_changes"], [])

    def test_percent_and_fixed_coupons(self):
        pid = self.make_product(price=20000)
        self.c.post("/api/v1/cart/items", {"product_id": pid})
        for code, kind, value, pct in (("FIJO", "fixed", 5000, 0), ("PCT", "percent", 0, 25)):
            self.db.insert("""INSERT INTO coupons (code, kind, value_cents, percent, per_user_limit, is_active, created_at, updated_at)
                              VALUES (?, ?, ?, ?, 1, TRUE, ?, ?)""", (code, kind, value, pct, now_iso(), now_iso()))
        q = self.c.post("/api/v1/cart/preview", {"coupon_code": "fijo"}).get_json()
        self.assertEqual(q["discount_cents"], 5000)
        q = self.c.post("/api/v1/cart/preview", {"coupon_code": "PCT"}).get_json()
        self.assertEqual(q["discount_cents"], 5000)
        self.assertEqual(q["total_cents"], 15000)

    def test_expired_and_min_subtotal_coupons(self):
        pid = self.make_product(price=5000)
        self.c.post("/api/v1/cart/items", {"product_id": pid})
        self.db.insert("""INSERT INTO coupons (code, kind, value_cents, ends_at, is_active, created_at, updated_at)
                          VALUES ('VIEJO', 'fixed', 1000, '2020-01-01T00:00:00+00:00', TRUE, ?, ?)""", (now_iso(), now_iso()))
        self.db.insert("""INSERT INTO coupons (code, kind, value_cents, min_subtotal_cents, is_active, created_at, updated_at)
                          VALUES ('MINIMO', 'fixed', 1000, 100000, TRUE, ?, ?)""", (now_iso(), now_iso()))
        for code in ("VIEJO", "MINIMO", "NOEXISTE"):
            q = self.c.post("/api/v1/cart/preview", {"coupon_code": code}).get_json()
            self.assertEqual(q["discount_cents"], 0)
            self.assertTrue(any(i["code"] == "coupon_invalid" for i in q["issues"]))

    def test_automatic_promotion_best_single_discount(self):
        cat = self.db.insert("INSERT INTO categories (name, slug, created_at, updated_at) VALUES ('C', 'c', ?, ?)", (now_iso(), now_iso()))
        pid = self.make_product(price=10000, category_id=cat)
        self.db.insert("""INSERT INTO promotions (name, kind, value, target, target_id, is_active, created_at, updated_at)
                          VALUES ('10', 'percent', 10, 'category', ?, TRUE, ?, ?)""", (cat, now_iso(), now_iso()))
        self.db.insert("""INSERT INTO promotions (name, kind, value, target, target_id, is_active, created_at, updated_at)
                          VALUES ('Q20', 'fixed', 2000, 'product', ?, TRUE, ?, ?)""", (pid, now_iso(), now_iso()))
        product = self.c.get(f"/api/v1/products/{self.db.scalar('SELECT slug FROM products WHERE id = ?', (pid,))}").get_json()
        self.assertEqual(product["price_cents"], 8000)
        self.assertEqual(product["compare_at_cents"], 10000)

    def test_shipping_and_free_shipping_threshold(self):
        pid = self.make_product(price=10000)
        self.c.post("/api/v1/cart/items", {"product_id": pid})
        q = self.c.post("/api/v1/cart/preview", {"shipping_method": "standard"}).get_json()
        self.assertEqual(q["shipping_cents"], 3000)
        from app.services import settings_service
        settings_service.update("shipping", {"free_shipping_over_cents": 5000})
        q = self.c.post("/api/v1/cart/preview", {"shipping_method": "standard"}).get_json()
        self.assertEqual(q["shipping_cents"], 0)

    def test_points_blocks_and_cap(self):
        pid = self.make_product(price=20000)  # Q200
        self.c.post("/api/v1/cart/items", {"product_id": pid})
        self.give_points(self.email, 5000)
        # 1000 pts = Q50; tope 50% de Q200 = Q100 -> máximo 2000 pts
        q = self.c.post("/api/v1/cart/preview", {"points_to_use": 5000}).get_json()
        self.assertEqual(q["points_used"], 2000)
        self.assertEqual(q["points_discount_cents"], 10000)
        q = self.c.post("/api/v1/cart/preview", {"points_to_use": 1500}).get_json()
        self.assertEqual(q["points_used"], 1000)

    def test_cannot_use_more_points_than_balance(self):
        pid = self.make_product(price=50000)
        self.c.post("/api/v1/cart/items", {"product_id": pid})
        self.give_points(self.email, 1000)
        q = self.c.post("/api/v1/cart/preview", {"points_to_use": 3000}).get_json()
        self.assertEqual(q["points_used"], 1000)
        self.assertFalse(q["can_checkout"])

    def test_guest_quote_and_merge(self):
        pid = self.make_product(price=3000, stock=4)
        guest = self.client()
        q = guest.post("/api/v1/cart/quote", {"items": [{"product_id": pid, "quantity": 2, "price_cents": 1}]}).get_json()
        self.assertEqual(q["subtotal_cents"], 6000)
        cart = self.c.post("/api/v1/cart/merge", {"items": [{"product_id": pid, "quantity": 99}]}).get_json()
        self.assertEqual(cart["lines"][0]["quantity"], 4)  # ajustado al stock
