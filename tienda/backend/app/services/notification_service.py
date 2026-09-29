"""Correos de la tienda.

Backends (variable MAIL_BACKEND):
- console : escribe el correo en el log (desarrollo, valor por defecto).
- smtp    : envío real por SMTP. Configurado para Gmail (smtp.gmail.com:587 +
            contraseña de aplicación). Sirve igual para Outlook o un dominio propio.
- memory  : guarda los correos en memoria (pruebas automáticas).

Un fallo de correo NUNCA interrumpe una compra: se registra en el log y ya.
Para WhatsApp o notificaciones push se agregaría otro canal con la misma idea.
"""
from __future__ import annotations

import html
import logging
import smtplib
import ssl
import threading
from email.message import EmailMessage
from email.utils import formataddr, make_msgid

from flask import current_app

log = logging.getLogger("app.notifications")


class ConsoleMailer:
    def send(self, to, subject, text, html_body=None):
        log.info("EMAIL to=%s subject=%s\n%s", to, subject, text)


class MemoryMailer:
    """Usado en pruebas para inspeccionar correos enviados."""
    outbox: list = []
    _lock = threading.Lock()

    def send(self, to, subject, text, html_body=None):
        with self._lock:
            self.outbox.append({"to": to, "subject": subject, "body": text, "html": html_body})


class SMTPMailer:
    def send(self, to, subject, text, html_body=None):
        cfg = current_app.config
        if not cfg.get("SMTP_USER") or not cfg.get("SMTP_PASSWORD"):
            raise RuntimeError("Faltan SMTP_USER o SMTP_PASSWORD en la configuración")
        from app.services import settings_service
        store_name = settings_service.get("store").get("name") or "Tienda"
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = formataddr((cfg.get("MAIL_FROM_NAME") or store_name, cfg.get("MAIL_FROM") or cfg["SMTP_USER"]))
        msg["To"] = to
        msg["Message-ID"] = make_msgid()
        reply_to = settings_service.get("contact").get("email")
        if reply_to:
            msg["Reply-To"] = reply_to
        msg.set_content(text)
        if html_body:
            msg.add_alternative(html_body, subtype="html")
        context = ssl.create_default_context()
        port = int(cfg.get("SMTP_PORT", 587))
        if port == 465:
            with smtplib.SMTP_SSL(cfg["SMTP_HOST"], port, context=context, timeout=15) as s:
                s.login(cfg["SMTP_USER"], cfg["SMTP_PASSWORD"])
                s.send_message(msg)
        else:
            with smtplib.SMTP(cfg["SMTP_HOST"], port, timeout=15) as s:
                s.starttls(context=context)
                s.login(cfg["SMTP_USER"], cfg["SMTP_PASSWORD"])
                s.send_message(msg)


BACKENDS = {"console": ConsoleMailer, "memory": MemoryMailer, "smtp": SMTPMailer}


def _deliver(backend, to, subject, text, html_body) -> bool:
    try:
        backend.send(to, subject, text, html_body)
        return True
    except Exception:  # un fallo de correo nunca debe romper una compra
        log.exception("No se pudo enviar el correo a %s", to)
        return False


def send_email(to: str, subject: str, text: str, html_body: str | None = None, *, wait: bool = False) -> bool:
    """Envía un correo. Con SMTP se envía en segundo plano (un hilo aparte)
    para que el cliente no espere 1-2 segundos a Gmail al confirmar su compra.
    wait=True espera el resultado (se usa en el correo de prueba del panel)."""
    name = current_app.config.get("MAIL_BACKEND", "console")
    backend = BACKENDS.get(name, ConsoleMailer)()
    if name != "smtp" or wait:
        return _deliver(backend, to, subject, text, html_body)
    app = current_app._get_current_object()

    def job():
        with app.app_context():
            _deliver(backend, to, subject, text, html_body)

    threading.Thread(target=job, name="mail", daemon=True).start()
    return True


# ------------------------------------------------------------------ plantillas
def _money(cents: int, symbol: str) -> str:
    return f"{symbol} {cents / 100:,.2f}"


def _layout(title: str, intro: str, body_html: str, button: tuple[str, str] | None = None) -> str:
    """Plantilla HTML de correo: estilos en línea (los clientes de correo
    ignoran las hojas de estilo) y todo el contenido dinámico escapado."""
    from app.services import settings_service
    s = settings_service.all_settings()
    store = html.escape(s["store"].get("name") or "Tienda")
    ink = s["theme"].get("primary") or "#1D2B36"
    accent = s["theme"].get("accent") or "#1F7A63"
    btn = ""
    if button:
        btn = (f'<p style="margin:28px 0 8px"><a href="{html.escape(button[1], quote=True)}" '
               f'style="background:{accent};color:#fff;text-decoration:none;padding:13px 22px;border-radius:6px;'
               f'font-weight:700;display:inline-block">{html.escape(button[0])}</a></p>')
    contact = s["contact"]
    foot = " · ".join(html.escape(x) for x in (contact.get("whatsapp"), contact.get("email")) if x)
    return f"""<!doctype html><html lang="es"><body style="margin:0;background:#F6F7F5;font-family:Arial,Helvetica,sans-serif;color:{ink}">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#F6F7F5;padding:24px 12px"><tr><td align="center">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:560px;background:#fff;border-radius:10px;overflow:hidden;border:1px solid #DDE2DF">
<tr><td style="background:{ink};padding:22px 28px;color:#fff;font-size:20px;font-weight:800;letter-spacing:-.3px">{store}</td></tr>
<tr><td style="padding:28px">
<h1 style="margin:0 0 12px;font-size:22px;line-height:1.25">{html.escape(title)}</h1>
<p style="margin:0 0 18px;font-size:15px;line-height:1.55;color:#3B4A55">{html.escape(intro)}</p>
{body_html}{btn}
</td></tr>
<tr><td style="padding:18px 28px;border-top:1px solid #DDE2DF;font-size:12px;color:#5B6770">{store}{(' · ' + foot) if foot else ''}</td></tr>
</table></td></tr></table></body></html>"""


def _order_table(order: dict, symbol: str) -> str:
    rows = "".join(
        f'<tr><td style="padding:8px 0;border-bottom:1px solid #EEF1EF;font-size:14px">{i["quantity"]} × {html.escape(i["product_name"])}</td>'
        f'<td align="right" style="padding:8px 0;border-bottom:1px solid #EEF1EF;font-size:14px">{_money(i["line_total_cents"], symbol)}</td></tr>'
        for i in order["items"])
    def line(label, cents, strong=False, minus=False):
        w = "700" if strong else "400"
        return (f'<tr><td style="padding:4px 0;font-size:14px;font-weight:{w}">{label}</td>'
                f'<td align="right" style="padding:4px 0;font-size:14px;font-weight:{w}">{"−" if minus else ""}{_money(cents, symbol)}</td></tr>')
    extra = line("Subtotal", order["subtotal_cents"])
    if order["discount_cents"]:
        extra += line("Descuento", order["discount_cents"], minus=True)
    if order["points_discount_cents"]:
        extra += line(f"Puntos ({order['points_used']:,})", order["points_discount_cents"], minus=True)
    extra += line("Envío", order["shipping_cents"]) + line("Total", order["total_cents"], strong=True)
    return f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0">{rows}</table><table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin-top:10px">{extra}</table>'


def _text_order(order: dict, symbol: str) -> str:
    lines = "\n".join(f"- {i['quantity']} x {i['product_name']}: {_money(i['line_total_cents'], symbol)}" for i in order["items"])
    return f"{lines}\n\nTotal: {_money(order['total_cents'], symbol)}"


def _ctx():
    from app.services import settings_service
    s = settings_service.all_settings()
    return s, s["store"].get("currency_symbol") or "Q", current_app.config["PUBLIC_BASE_URL"]


def notify_order_created(order: dict) -> None:
    s, sym, base = _ctx()
    payment = (order.get("payment") or {}).get("instructions") or ""
    link = f"{base}/cuenta/pedidos/{order['order_number']}"
    extra = f'<p style="margin:18px 0 0;padding:12px 14px;background:#EAF0F4;border-radius:6px;font-size:14px">{html.escape(payment)}</p>' if payment else ""
    if order.get("points_earned"):
        extra += f'<p style="margin:14px 0 0;font-size:14px;color:#7A5516"><b>Sumarás {order["points_earned"]:,} puntos</b> cuando recibas tu pedido.</p>'
    send_email(
        order["customer_email"], f"Recibimos tu pedido {order['order_number']}",
        f"Gracias por tu compra.\n\n{_text_order(order, sym)}\n\n{payment}\n\nVer pedido: {link}",
        _layout("¡Gracias por tu compra!", f"Recibimos tu pedido {order['order_number']}. Te avisaremos cuando cambie de estado.",
                _order_table(order, sym) + extra, ("Ver mi pedido", link)),
    )
    # Aviso al dueño y a su equipo.
    recipients = [e.strip() for e in (s.get("notifications", {}).get("new_order_emails") or "").split(",") if e.strip()]
    if recipients:
        admin_link = f"{base}/admin/pedidos/{order['id']}"
        from app.payments.registry import PROVIDERS
        ship = next((m["label"] for m in s["shipping"].get("methods", []) if m["code"] == order["shipping_method"]), order["shipping_method"])
        pay = PROVIDERS[order["payment_provider"]].label if order["payment_provider"] in PROVIDERS else order["payment_provider"]
        who = f"{order['customer_name']} ({order['customer_email']}{', ' + order['customer_phone'] if order.get('customer_phone') else ''})"
        body = (f'<p style="margin:0 0 14px;font-size:14px"><b>Cliente:</b> {html.escape(who)}<br>'
                f'<b>Entrega:</b> {html.escape(ship)}<br><b>Pago:</b> {html.escape(pay)}</p>'
                + _order_table(order, sym))
        for to in recipients:
            send_email(to, f"Nuevo pedido {order['order_number']} · {_money(order['total_cents'], sym)}",
                       f"Nuevo pedido de {who}.\n\n{_text_order(order, sym)}\n\nVer en el panel: {admin_link}",
                       _layout("Tienes un pedido nuevo", f"Pedido {order['order_number']} por {_money(order['total_cents'], sym)}.",
                               body, ("Ver en el panel", admin_link)))


def notify_status_changed(order: dict) -> None:
    _, sym, base = _ctx()
    link = f"{base}/cuenta/pedidos/{order['order_number']}"
    messages = {
        "paid": "Confirmamos tu pago.", "preparing": "Estamos preparando tu pedido.",
        "shipped": "Tu pedido va en camino.", "delivered": "Tu pedido fue entregado. ¡Gracias por comprar con nosotros!",
        "cancelled": "Tu pedido fue cancelado. Si usaste puntos, ya se devolvieron a tu tarjeta.",
    }
    intro = messages.get(order["status"], f"El estado de tu pedido ahora es: {order['status_label']}.")
    send_email(order["customer_email"], f"Tu pedido {order['order_number']}: {order['status_label']}",
               f"{intro}\n\nVer pedido: {link}",
               _layout(f"Pedido {order['status_label'].lower()}", intro, "", ("Ver mi pedido", link)))


def notify_welcome(email: str, first_name: str) -> None:
    s, _, base = _ctx()
    l = s["loyalty"]
    extra = ""
    if l.get("enabled"):
        extra = (f'<p style="margin:0;font-size:14px;line-height:1.55">Tu tarjeta virtual de <b>{html.escape(l.get("program_name") or "puntos")}</b> '
                 f'ya está activa: sumas puntos con cada compra y los canjeas por descuentos.</p>')
    send_email(email, f"Bienvenido a {s['store'].get('name') or 'la tienda'}",
               f"Hola {first_name}, tu cuenta está lista. {base}",
               _layout(f"Hola, {first_name}", "Tu cuenta está lista.", extra, ("Ir a la tienda", base)))


def notify_password_reset(email: str, first_name: str, link: str) -> None:
    send_email(email, "Restablece tu contraseña",
               f"Hola {first_name},\n\nUsa este enlace para crear una contraseña nueva (válido 1 hora):\n{link}\n\nSi no lo solicitaste, ignora este mensaje.",
               _layout("Restablece tu contraseña", f"Hola {first_name}, usa el botón para crear una contraseña nueva. El enlace vence en 1 hora. Si no lo solicitaste, ignora este mensaje.",
                       "", ("Crear contraseña nueva", link)))


def send_test(to: str) -> bool:
    return send_email(to, "Correo de prueba", "Si recibes este mensaje, el correo de la tienda funciona.",
                      _layout("¡El correo funciona!", "Si recibes este mensaje, la tienda ya puede enviar confirmaciones de pedido y avisos.", ""),
                      wait=True)
