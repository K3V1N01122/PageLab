"""Notificaciones. El proveedor de correo aún no está definido: el backend
`console` escribe el mensaje en el log. Para producción, implemente un backend
nuevo (SMTP, SES, Resend...) registrándolo en BACKENDS. WhatsApp y push se
añadirían como canales adicionales con la misma interfaz."""
import logging
import threading

from flask import current_app

log = logging.getLogger("app.notifications")


class ConsoleMailer:
    def send(self, to: str, subject: str, body: str) -> None:
        log.info("EMAIL to=%s subject=%s\n%s", to, subject, body)


class MemoryMailer:
    """Usado en pruebas para inspeccionar correos enviados."""
    outbox: list = []
    _lock = threading.Lock()

    def send(self, to, subject, body):
        with self._lock:
            self.outbox.append({"to": to, "subject": subject, "body": body})


BACKENDS = {"console": ConsoleMailer, "memory": MemoryMailer}


def send_email(to: str, subject: str, body: str) -> None:
    backend = BACKENDS.get(current_app.config.get("MAIL_BACKEND", "console"), ConsoleMailer)()
    try:
        backend.send(to, subject, body)
    except Exception:  # un fallo de correo nunca debe romper una compra
        log.exception("No se pudo enviar el correo a %s", to)
