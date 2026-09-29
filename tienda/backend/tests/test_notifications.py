from app.services.notification_service import MemoryMailer
from tests.helpers import BaseTest


class NotificationTests(BaseTest):
    def test_welcome_email_on_register(self):
        c = self.client()
        c.register("nuevo@example.com")
        mail = MemoryMailer.outbox[-1]
        self.assertEqual(mail["to"], "nuevo@example.com")
        self.assertIn("Bienvenido", mail["subject"])
        self.assertIn("<html", mail["html"])

    def test_order_emails_to_customer_and_owner(self):
        admin = self.make_admin()
        r = admin.put("/api/v1/admin/settings/notifications", {"new_order_emails": "Dueno@Example.com, ventas@example.com"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json()["new_order_emails"], "dueno@example.com, ventas@example.com")
        c = self.client()
        email = c.register()
        pid = self.make_product(name="Camisa <b>azul</b>", price=12000)
        c.post("/api/v1/cart/items", {"product_id": pid})
        MemoryMailer.outbox.clear()
        order = self.checkout(c).get_json()
        to = sorted(m["to"] for m in MemoryMailer.outbox)
        self.assertEqual(to, sorted([email, "dueno@example.com", "ventas@example.com"]))
        owner = next(m for m in MemoryMailer.outbox if m["to"] == "dueno@example.com")
        self.assertIn(order["order_number"], owner["subject"])
        # El contenido dinámico se escapa en el HTML del correo
        self.assertNotIn("<b>azul</b>", owner["html"])
        self.assertIn("&lt;b&gt;azul&lt;/b&gt;", owner["html"])

    def test_status_change_email(self):
        admin = self.make_admin()
        c = self.client()
        email = c.register()
        pid = self.make_product()
        c.post("/api/v1/cart/items", {"product_id": pid})
        order = self.checkout(c).get_json()
        MemoryMailer.outbox.clear()
        admin.post(f"/api/v1/admin/orders/{order['id']}/status", {"status": "preparing"})
        self.assertEqual(MemoryMailer.outbox[-1]["to"], email)
        self.assertIn("Preparando", MemoryMailer.outbox[-1]["subject"])

    def test_invalid_notification_emails_rejected(self):
        admin = self.make_admin()
        r = admin.put("/api/v1/admin/settings/notifications", {"new_order_emails": "no-es-correo"})
        self.assertEqual(r.status_code, 422)

    def test_test_email_endpoint(self):
        admin = self.make_admin()
        r = admin.post("/api/v1/admin/settings/test-email", {"to": "prueba@example.com"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(MemoryMailer.outbox[-1]["to"], "prueba@example.com")
        customer = self.client()
        customer.register()
        self.assertEqual(customer.post("/api/v1/admin/settings/test-email", {"to": "x@example.com"}).status_code, 403)

    def test_notification_emails_not_public(self):
        admin = self.make_admin()
        admin.put("/api/v1/admin/settings/notifications", {"new_order_emails": "privado@example.com"})
        self.assertNotIn("privado@example.com", self.client().get("/api/v1/config").get_data(as_text=True))
