"""Utilidades de prueba: app aislada por prueba sobre un archivo SQLite
temporal (permite probar concurrencia real entre hilos)."""
import os
import tempfile
import unittest
import uuid

from app import create_app
from app.core.timeutil import now_iso
from app.db import get_db
from app.services import settings_service, promotion_service, catalog_service
from app.services.notification_service import MemoryMailer


class ApiClient:
    """Cliente que gestiona la cookie CSRF como lo hace el navegador."""

    def __init__(self, app):
        self.app = app
        self.c = app.test_client()
        self.c.get("/api/v1/health")

    def _headers(self, extra=None):
        cookie = self.c.get_cookie("csrf_token")
        h = {"X-CSRF-Token": cookie.value if cookie else ""}
        h.update(extra or {})
        return h

    def get(self, url, **kw):
        return self.c.get(url, **kw)

    def post(self, url, json=None, headers=None, **kw):
        return self.c.post(url, json=json if json is not None else {}, headers=self._headers(headers), **kw)

    def put(self, url, json=None, **kw):
        return self.c.put(url, json=json or {}, headers=self._headers(), **kw)

    def patch(self, url, json=None, **kw):
        return self.c.patch(url, json=json or {}, headers=self._headers(), **kw)

    def delete(self, url, **kw):
        return self.c.delete(url, headers=self._headers(), **kw)

    def register(self, email=None, password="Clave1234", **extra):
        email = email or f"u{uuid.uuid4().hex[:8]}@example.com"
        r = self.post("/api/v1/auth/register", {
            "first_name": "Ana", "last_name": "Prueba", "email": email, "password": password,
            "password_confirm": password, "accept_terms": True, **extra})
        assert r.status_code == 201, r.get_json()
        return email

    def login(self, email, password="Clave1234"):
        r = self.post("/api/v1/auth/login", {"email": email, "password": password})
        assert r.status_code == 200, r.get_json()
        return r


class BaseTest(unittest.TestCase):
    def setUp(self):
        fd, self.db_path = tempfile.mkstemp(suffix=".sqlite3")
        os.close(fd)
        self.upload_dir = tempfile.mkdtemp()
        settings_service.invalidate()
        promotion_service.invalidate()
        catalog_service.invalidate_categories()
        MemoryMailer.outbox.clear()
        # Con TEST_DATABASE_URL=postgresql://... las pruebas corren sobre PostgreSQL
        # (se recrea el esquema en cada prueba; use una base exclusiva para pruebas).
        pg_url = os.getenv("TEST_DATABASE_URL", "")
        if pg_url.startswith("postgres"):
            import psycopg
            with psycopg.connect(pg_url, autocommit=True) as conn:
                conn.execute("DROP SCHEMA public CASCADE")
                conn.execute("CREATE SCHEMA public")
        db_url = pg_url if pg_url.startswith("postgres") else f"sqlite:///{self.db_path}"
        self.app = create_app("testing", {
            "DATABASE_URL": db_url, "MAIL_BACKEND": "memory",
            "UPLOAD_DIR": __import__("pathlib").Path(self.upload_dir),
        })
        self.ctx = self.app.app_context()
        self.ctx.push()
        self.db = get_db()

    def tearDown(self):
        self.ctx.pop()
        for suffix in ("", "-wal", "-shm"):
            try:
                os.remove(self.db_path + suffix)
            except FileNotFoundError:
                pass
        settings_service.invalidate()
        promotion_service.invalidate()
        catalog_service.invalidate_categories()

    def client(self):
        return ApiClient(self.app)

    def make_admin(self, email="admin@example.com", password="Admin1234"):
        c = self.client()
        c.register(email, password)
        self.db.execute("UPDATE users SET role_id = (SELECT id FROM roles WHERE code = 'admin') WHERE email = ?", (email,))
        c.login(email, password)
        return c

    def make_product(self, name="Producto test", price=10000, stock=10, status="active", category_id=None, compare=None):
        sku = "T-" + uuid.uuid4().hex[:8].upper()
        slug = sku.lower()
        pid = self.db.insert(
            """INSERT INTO products (category_id, name, slug, sku, price_cents, compare_at_cents, stock, status,
                   search_text, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (category_id, name, slug, sku, price, compare, stock, status, name.lower(), now_iso(), now_iso()))
        return pid

    def user_id(self, email):
        return self.db.scalar("SELECT id FROM users WHERE email = ?", (email,))

    def give_points(self, email, points):
        uid = self.user_id(email)
        self.db.execute("UPDATE loyalty_cards SET points_balance = ? WHERE user_id = ?", (points, uid))

    def checkout(self, c, **overrides):
        body = {"idempotency_key": uuid.uuid4().hex, "shipping_method": "pickup",
                "payment_provider": "cash_on_delivery", **overrides}
        return c.post("/api/v1/checkout", body)
