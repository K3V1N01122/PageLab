from tests.helpers import BaseTest
from app.services.notification_service import MemoryMailer


class AuthTests(BaseTest):
    def test_register_creates_user_hashed_password_and_loyalty_card(self):
        c = self.client()
        email = c.register("nueva@example.com")
        row = self.db.one("SELECT password_hash FROM users WHERE email = ?", (email,))
        self.assertNotIn("Clave1234", row["password_hash"])
        self.assertTrue(row["password_hash"].startswith("scrypt:"))
        card = c.get("/api/v1/loyalty/card").get_json()
        self.assertEqual(card["points_available"], 0)
        self.assertRegex(card["card_number"], r"^[A-Z2-9]{4}-[A-Z2-9]{4}-[A-Z2-9]{4}$")

    def test_register_validations(self):
        c = self.client()
        r = c.post("/api/v1/auth/register", {"first_name": "A", "last_name": "B", "email": "mal",
                                              "password": "corta", "password_confirm": "otra", "accept_terms": False})
        self.assertEqual(r.status_code, 422)
        details = r.get_json()["error"]["details"]
        self.assertIn("email", details)
        self.assertIn("password", details)

    def test_duplicate_email_rejected(self):
        c = self.client()
        c.register("dup@example.com")
        c2 = self.client()
        r = c2.post("/api/v1/auth/register", {"first_name": "A", "last_name": "B", "email": "DUP@example.com",
                                               "password": "Clave1234", "password_confirm": "Clave1234", "accept_terms": True})
        self.assertEqual(r.status_code, 409)

    def test_terms_must_be_accepted(self):
        c = self.client()
        r = c.post("/api/v1/auth/register", {"first_name": "A", "last_name": "B", "email": "t@example.com",
                                              "password": "Clave1234", "password_confirm": "Clave1234", "accept_terms": False})
        self.assertEqual(r.status_code, 422)
        self.assertIn("accept_terms", r.get_json()["error"]["details"])

    def test_login_logout_and_session_cookie_flags(self):
        c = self.client()
        email = c.register()
        c.post("/api/v1/auth/logout")
        self.assertIsNone(c.get("/api/v1/auth/me").get_json()["user"])
        r = c.login(email)
        cookie_header = [h for h in r.headers.getlist("Set-Cookie") if h.startswith("sid=")][0]
        self.assertIn("HttpOnly", cookie_header)
        self.assertIn("SameSite=Lax", cookie_header)
        self.assertEqual(c.get("/api/v1/auth/me").get_json()["user"]["email"], email)
        c.post("/api/v1/auth/logout")
        self.assertIsNone(c.get("/api/v1/auth/me").get_json()["user"])

    def test_session_token_stored_hashed(self):
        c = self.client()
        c.register()
        token = c.c.get_cookie("sid").value
        self.assertIsNone(self.db.one("SELECT id FROM sessions WHERE token_hash = ?", (token,)))

    def test_wrong_password_generic_message_and_lockout(self):
        c = self.client()
        email = c.register()
        for _ in range(5):
            r = c.post("/api/v1/auth/login", {"email": email, "password": "Incorrecta1"})
            self.assertEqual(r.status_code, 401)
        r = c.post("/api/v1/auth/login", {"email": email, "password": "Clave1234"})
        self.assertEqual(r.get_json()["error"]["code"], "account_locked")

    def test_unknown_email_same_error_as_wrong_password(self):
        c = self.client()
        r = c.post("/api/v1/auth/login", {"email": "nadie@example.com", "password": "Clave1234"})
        self.assertEqual(r.get_json()["error"]["code"], "invalid_credentials")

    def test_password_reset_flow(self):
        c = self.client()
        email = c.register()
        c.post("/api/v1/auth/logout")
        r = c.post("/api/v1/auth/password/forgot", {"email": email})
        self.assertEqual(r.status_code, 200)
        body = MemoryMailer.outbox[-1]["body"]
        token = body.split("token=")[1].split()[0]
        r = c.post("/api/v1/auth/password/reset", {"token": token, "password": "Nueva1234", "password_confirm": "Nueva1234"})
        self.assertEqual(r.status_code, 200)
        # el token es de un solo uso
        r = c.post("/api/v1/auth/password/reset", {"token": token, "password": "Otra12345", "password_confirm": "Otra12345"})
        self.assertEqual(r.status_code, 422)
        c.login(email, "Nueva1234")

    def test_forgot_password_does_not_reveal_accounts(self):
        c = self.client()
        r = c.post("/api/v1/auth/password/forgot", {"email": "noexiste@example.com"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(MemoryMailer.outbox), 0)

    def test_change_password_revokes_other_sessions(self):
        a = self.client()
        email = a.register()
        b = self.client()
        b.login(email)
        r = a.post("/api/v1/auth/password/change", {"current_password": "Clave1234", "password": "Nueva1234", "password_confirm": "Nueva1234"})
        self.assertEqual(r.status_code, 200)
        self.assertIsNotNone(a.get("/api/v1/auth/me").get_json()["user"])
        self.assertIsNone(b.get("/api/v1/auth/me").get_json()["user"])

    def test_disabled_user_cannot_login(self):
        c = self.client()
        email = c.register()
        self.db.execute("UPDATE users SET is_active = FALSE WHERE email = ?", (email,))
        self.assertIsNone(c.get("/api/v1/auth/me").get_json()["user"])
        r = c.post("/api/v1/auth/login", {"email": email, "password": "Clave1234"})
        self.assertEqual(r.get_json()["error"]["code"], "account_disabled")
