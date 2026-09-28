"""Operaciones simultáneas reales (hilos + conexiones independientes)."""
import threading
import uuid

from app.core.timeutil import now_iso
from tests.helpers import BaseTest


def run_parallel(fns):
    results = [None] * len(fns)
    barrier = threading.Barrier(len(fns))

    def worker(i, fn):
        barrier.wait()
        results[i] = fn()

    threads = [threading.Thread(target=worker, args=(i, fn)) for i, fn in enumerate(fns)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(60)
    return results


class ConcurrencyTests(BaseTest):
    def test_no_overselling_under_concurrent_checkouts(self):
        pid = self.make_product(price=5000, stock=5)
        clients = []
        for _ in range(20):
            c = self.client()
            c.register()
            c.post("/api/v1/cart/items", {"product_id": pid, "quantity": 1})
            clients.append(c)
        results = run_parallel([lambda c=c: self.checkout(c).status_code for c in clients])
        self.assertEqual(results.count(201), 5, results)
        self.assertTrue(all(r in (201, 409) for r in results), results)
        self.assertEqual(self.db.scalar("SELECT stock FROM products WHERE id = ?", (pid,)), 0)
        self.assertEqual(self.db.scalar("SELECT COUNT(*) AS n FROM orders"), 5)
        self.assertEqual(self.db.scalar("SELECT COALESCE(SUM(delta), 0) AS n FROM inventory_movements WHERE product_id = ?", (pid,)), -5)

    def test_duplicate_checkout_requests_create_one_order(self):
        pid = self.make_product(stock=10)
        c = self.client()
        c.register()
        c.post("/api/v1/cart/items", {"product_id": pid, "quantity": 1})
        key = uuid.uuid4().hex
        results = run_parallel([lambda: self.checkout(c, idempotency_key=key).get_json().get("order_number")] * 6)
        self.assertEqual(len(set(results)), 1, results)
        self.assertEqual(self.db.scalar("SELECT COUNT(*) AS n FROM orders"), 1)
        self.assertEqual(self.db.scalar("SELECT stock FROM products WHERE id = ?", (pid,)), 9)

    def test_points_cannot_be_double_spent(self):
        c = self.client()
        email = c.register()
        self.give_points(email, 1000)
        rid = self.db.insert("""INSERT INTO rewards (name, kind, points_cost, value_cents, is_active, created_at, updated_at)
                                VALUES ('Q50', 'fixed_discount', 1000, 5000, TRUE, ?, ?)""", (now_iso(), now_iso()))
        results = run_parallel([lambda: c.post(f"/api/v1/rewards/{rid}/redeem", {"idempotency_key": uuid.uuid4().hex}).status_code] * 8)
        self.assertEqual(results.count(201), 1, results)
        self.assertEqual(self.db.scalar("SELECT points_balance FROM loyalty_cards WHERE user_id = ?", (self.user_id(email),)), 0)
        self.assertEqual(self.db.scalar("SELECT COUNT(*) AS n FROM coupons"), 1)

    def test_limited_coupon_under_concurrency(self):
        pid = self.make_product(stock=50)
        self.db.insert("""INSERT INTO coupons (code, kind, value_cents, max_uses, per_user_limit, is_active, created_at, updated_at)
                          VALUES ('TRES', 'fixed', 500, 3, 1, TRUE, ?, ?)""", (now_iso(), now_iso()))
        clients = []
        for _ in range(10):
            c = self.client()
            c.register()
            c.post("/api/v1/cart/items", {"product_id": pid})
            clients.append(c)
        results = run_parallel([lambda c=c: self.checkout(c, coupon_code="TRES").status_code for c in clients])
        self.assertEqual(results.count(201), 3, results)
        self.assertEqual(self.db.scalar("SELECT uses_count FROM coupons WHERE code = 'TRES'"), 3)
