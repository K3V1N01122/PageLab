from tests.helpers import BaseTest


ADMIN_ENDPOINTS = [
    ("get", "/api/v1/admin/products"), ("post", "/api/v1/admin/products"), ("get", "/api/v1/admin/orders"),
    ("get", "/api/v1/admin/users"), ("get", "/api/v1/admin/stats"), ("get", "/api/v1/admin/settings"),
    ("post", "/api/v1/admin/coupons"), ("get", "/api/v1/admin/rewards"), ("put", "/api/v1/admin/loyalty/settings"),
]


class PermissionTests(BaseTest):
    def test_anonymous_and_customers_blocked_from_admin(self):
        anon = self.client()
        customer = self.client()
        customer.register()
        for method, url in ADMIN_ENDPOINTS:
            self.assertEqual(getattr(anon, method)(url).status_code, 401, url)
            self.assertEqual(getattr(customer, method)(url).status_code, 403, url)

    def test_admin_access(self):
        admin = self.make_admin()
        for method, url in ADMIN_ENDPOINTS:
            if method == "get":
                self.assertEqual(admin.get(url).status_code, 200, url)

    def test_limited_role_only_gets_its_permissions(self):
        c = self.client()
        email = c.register()
        self.db.execute("UPDATE users SET role_id = (SELECT id FROM roles WHERE code = 'inventory') WHERE email = ?", (email,))
        self.assertEqual(c.get("/api/v1/admin/products").status_code, 200)
        self.assertEqual(c.get("/api/v1/admin/users").status_code, 403)
        self.assertEqual(c.get("/api/v1/admin/settings").status_code, 403)

    def test_role_cannot_be_self_assigned(self):
        c = self.client()
        email = c.register(role="admin", role_id=2, is_staff=True)
        self.assertEqual(self.db.scalar(
            "SELECT r.code FROM users u JOIN roles r ON r.id = u.role_id WHERE u.email = ?", (email,)), "customer")
        c.put("/api/v1/account/profile", {"first_name": "A", "last_name": "B", "role": "admin"})
        self.assertEqual(c.get("/api/v1/admin/products").status_code, 403)

    def test_admin_cannot_demote_self_and_role_change_revokes_sessions(self):
        admin = self.make_admin()
        admin_id = self.user_id("admin@example.com")
        self.assertEqual(admin.patch(f"/api/v1/admin/users/{admin_id}", {"role": "customer"}).status_code, 403)
        c = self.client()
        email = c.register()
        uid = self.user_id(email)
        self.assertEqual(admin.patch(f"/api/v1/admin/users/{uid}", {"role": "inventory"}).status_code, 200)
        self.assertIsNone(c.get("/api/v1/auth/me").get_json()["user"])

    def test_admin_product_crud(self):
        admin = self.make_admin()
        r = admin.post("/api/v1/admin/products", {"name": "Nuevo", "sku": "nv-1", "price_cents": 1500, "stock": 4,
                                                  "status": "active", "tags": ["a", "b"], "attributes": {"Color": "Azul"}})
        self.assertEqual(r.status_code, 201, r.get_json())
        p = r.get_json()
        self.assertEqual(p["sku"], "NV-1")
        self.assertEqual(p["tags"], ["a", "b"])
        dup = admin.post("/api/v1/admin/products", {"name": "Otro", "sku": "NV-1", "price_cents": 1})
        self.assertEqual(dup.status_code, 409)
        r = admin.put(f"/api/v1/admin/products/{p['id']}", {**p, "price_cents": 2000, "stock": 9})
        self.assertEqual(r.get_json()["price_cents"], 2000)
        self.assertEqual(r.get_json()["stock"], 9)
        self.assertEqual(admin.post(f"/api/v1/admin/products/{p['id']}/stock", {"delta": -20}).status_code, 409)
        self.assertEqual(admin.post(f"/api/v1/admin/products/{p['id']}/stock", {"delta": -2}).get_json()["stock"], 7)
        public = self.client().get("/api/v1/products?q=nuevo").get_json()
        self.assertEqual(public["pagination"]["total"], 1)
        self.assertEqual(admin.delete(f"/api/v1/admin/products/{p['id']}").get_json()["result"], "deleted")

    def test_product_with_sales_is_archived_not_deleted(self):
        admin = self.make_admin()
        c = self.client()
        c.register()
        pid = self.make_product()
        c.post("/api/v1/cart/items", {"product_id": pid})
        self.assertEqual(self.checkout(c).status_code, 201)
        self.assertEqual(admin.delete(f"/api/v1/admin/products/{pid}").get_json()["result"], "archived")

    def test_image_upload_validates_content(self):
        import io
        from PIL import Image
        admin = self.make_admin()
        fake = (io.BytesIO(b"<?php echo 1; ?>"), "foto.jpg")
        r = admin.c.post("/api/v1/admin/uploads", data={"file": fake}, headers=admin._headers(),
                         content_type="multipart/form-data")
        self.assertEqual(r.status_code, 422)
        buf = io.BytesIO()
        Image.new("RGB", (1600, 800), (10, 120, 90)).save(buf, "PNG")
        buf.seek(0)
        r = admin.c.post("/api/v1/admin/uploads", data={"file": (buf, "ok.png")}, headers=admin._headers(),
                         content_type="multipart/form-data")
        self.assertEqual(r.status_code, 201, r.get_json())
        self.assertTrue(r.get_json()["url"].endswith("-lg.webp"))
