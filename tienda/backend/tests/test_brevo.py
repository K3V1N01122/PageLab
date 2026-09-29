"""Envío por Brevo contra un servidor HTTP local que imita su API."""
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from app.services import notification_service as ns
from tests.helpers import BaseTest


class FakeBrevo(BaseHTTPRequestHandler):
    received = []
    status = 201

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        FakeBrevo.received.append({"headers": dict(self.headers), "body": body})
        self.send_response(FakeBrevo.status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"messageId":"<x@relay>"}' if FakeBrevo.status < 300 else b'{"code":"unauthorized","message":"Key not found"}')

    def log_message(self, *a):
        pass


class BrevoTests(BaseTest):
    def setUp(self):
        super().setUp()
        self.server = HTTPServer(("127.0.0.1", 0), FakeBrevo)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self._url = ns.BrevoMailer.URL
        ns.BrevoMailer.URL = f"http://127.0.0.1:{self.server.server_port}/v3/smtp/email"
        FakeBrevo.received, FakeBrevo.status = [], 201
        self.app.config.update(MAIL_BACKEND="brevo", BREVO_API_KEY="xkeysib-test", MAIL_FROM="tienda@gmail.com")

    def tearDown(self):
        ns.BrevoMailer.URL = self._url
        self.server.shutdown()
        super().tearDown()

    def test_sends_through_brevo_api(self):
        admin = self.make_admin()
        FakeBrevo.received.clear()
        r = admin.post("/api/v1/admin/settings/test-email", {"to": "destino@example.com"})
        self.assertEqual(r.status_code, 200, r.get_json())
        req = FakeBrevo.received[-1]
        headers = {k.lower(): v for k, v in req["headers"].items()}  # los encabezados HTTP no distinguen mayúsculas
        self.assertEqual(headers["api-key"], "xkeysib-test")
        self.assertEqual(req["body"]["to"], [{"email": "destino@example.com"}])
        self.assertEqual(req["body"]["sender"]["email"], "tienda@gmail.com")
        self.assertIn("htmlContent", req["body"])

    def test_brevo_error_is_reported(self):
        admin = self.make_admin()
        FakeBrevo.status = 401
        r = admin.post("/api/v1/admin/settings/test-email", {"to": "destino@example.com"})
        self.assertEqual(r.status_code, 502)
