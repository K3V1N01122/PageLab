from tests.helpers import BaseTest


class SecurityTests(BaseTest):
    def test_csrf_required_for_unsafe_requests(self):
        c = self.client()
        r = c.c.post("/api/v1/auth/login", json={"email": "a@example.com", "password": "x"})
        self.assertEqual(r.status_code, 403)
        self.assertEqual(r.get_json()["error"]["code"], "csrf_failed")

    def test_foreign_origin_rejected(self):
        c = self.client()
        r = c.post("/api/v1/auth/login", {"email": "a@example.com", "password": "x"}, headers={"Origin": "https://evil.example"})
        self.assertEqual(r.status_code, 403)

    def test_security_headers(self):
        r = self.client().get("/api/v1/health")
        self.assertEqual(r.headers["X-Content-Type-Options"], "nosniff")
        self.assertEqual(r.headers["X-Frame-Options"], "DENY")
        self.assertIn("default-src 'self'", r.headers["Content-Security-Policy"])

    def test_sql_injection_in_search_is_inert(self):
        self.make_product("Taza azul")
        r = self.client().get("/api/v1/products?q=' OR 1=1; DROP TABLE products; --")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json()["pagination"]["total"], 0)
        self.assertIsNotNone(self.db.one("SELECT id FROM products LIMIT 1"))

    def test_errors_do_not_leak_internals(self):
        @self.app.get("/api/v1/_boom")
        def boom():
            raise RuntimeError("secreto interno")
        r = self.client().get("/api/v1/_boom")
        self.assertEqual(r.status_code, 500)
        self.assertNotIn("secreto", r.get_data(as_text=True))

    def test_rate_limit(self):
        self.app.config["RATE_LIMIT_ENABLED"] = True
        self.app.config["RATE_LIMIT_AUTH"] = "3/60"
        c = self.client()
        codes = [c.post("/api/v1/auth/login", {"email": "x@example.com", "password": "Clave1234"}).status_code for _ in range(5)]
        self.assertEqual(codes[-1], 429)

    def test_bearer_token_for_mobile_clients(self):
        c = self.client()
        email = c.register()
        r = c.post("/api/v1/auth/login", {"email": email, "password": "Clave1234"}, headers={"X-Client": "mobile"})
        token = r.get_json()["token"]
        raw = self.app.test_client()
        me = raw.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}).get_json()
        self.assertEqual(me["user"]["email"], email)
        # Con Bearer no se exige CSRF (no hay cookies implicadas)
        r = raw.post("/api/v1/account/favorites/999", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(r.status_code, 404)

    def test_seo_pages_and_404(self):
        pid = self.make_product("Silla")
        slug = self.db.scalar("SELECT slug FROM products WHERE id = ?", (pid,))
        c = self.client()
        r = c.get(f"/producto/{slug}")
        html = r.get_data(as_text=True)
        self.assertEqual(r.status_code, 200)
        self.assertIn("<title>Silla", html)
        self.assertIn("application/ld+json", html)
        self.assertEqual(c.get("/producto/no-existe").status_code, 404)
        self.assertEqual(c.get("/ruta-que-no-existe").status_code, 404)
        self.assertIn("<loc>", c.get("/sitemap.xml").get_data(as_text=True))
        self.assertIn("Disallow: /api/", c.get("/robots.txt").get_data(as_text=True))

    def test_meta_is_escaped(self):
        pid = self.make_product('<script>alert(1)</script>')
        slug = self.db.scalar("SELECT slug FROM products WHERE id = ?", (pid,))
        html = self.client().get(f"/producto/{slug}").get_data(as_text=True)
        self.assertNotIn("<script>alert(1)</script>", html)

    def test_settings_reject_dangerous_links(self):
        admin = self.make_admin()
        r = admin.put("/api/v1/admin/settings/social", {"instagram": "javascript:alert(1)"})
        self.assertEqual(r.status_code, 422)
        r = admin.put("/api/v1/admin/settings/social", {"instagram": "https://instagram.com/tienda"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(admin.put("/api/v1/admin/settings/theme", {"accent": "red;}"}).status_code, 422)
