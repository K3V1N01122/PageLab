"""Migraciones SQL versionadas + datos de referencia.

- Los archivos `migrations/NNNN_nombre.sql` se aplican en orden, una sola vez,
  y se registran en `schema_migrations`.
- `ensure_reference_data` crea (de forma idempotente) roles, permisos, estados
  de pedido y la configuración inicial. No crea productos ni usuarios: los
  datos de demostración están en `seeds/demo.py` y se cargan aparte.
"""
from __future__ import annotations

import json
from pathlib import Path

from app.core.timeutil import now_iso

MIGRATIONS_DIR = Path(__file__).parent / "migrations"

DIALECT_TOKENS = {
    "sqlite": {
        "{{ID}}": "INTEGER PRIMARY KEY AUTOINCREMENT",
        "{{BOOL}}": "BOOLEAN",
        "{{TS}}": "TEXT",
        "{{JSON}}": "TEXT",
    },
    "postgres": {
        "{{ID}}": "BIGSERIAL PRIMARY KEY",
        "{{BOOL}}": "BOOLEAN",
        "{{TS}}": "TIMESTAMPTZ",
        "{{JSON}}": "JSONB",
    },
}

# Permisos del sistema. Añadir aquí un permiso nuevo y asignarlo a roles.
PERMISSIONS = {
    "products.read": "Ver productos en el panel",
    "products.write": "Crear y editar productos, categorías e imágenes",
    "inventory.write": "Modificar stock",
    "orders.read": "Ver pedidos",
    "orders.update": "Cambiar el estado de pedidos",
    "users.read": "Ver clientes",
    "users.manage": "Activar, desactivar y cambiar roles de usuarios",
    "loyalty.manage": "Configurar puntos, recompensas y ajustes de puntos",
    "promotions.manage": "Crear cupones y promociones",
    "stats.read": "Ver estadísticas",
    "settings.manage": "Editar la configuración de la tienda",
}

ROLES = {
    # code: (nombre, es_staff, permisos)
    "customer": ("Cliente", False, []),
    "admin": ("Administrador", True, list(PERMISSIONS)),
    # Ejemplo de rol ampliado: ilustra cómo añadir roles sin tocar código.
    "inventory": ("Encargado de inventario", True, ["products.read", "products.write", "inventory.write", "orders.read"]),
}

ORDER_STATUSES = [
    # code, etiqueta, orden, final
    ("pending", "Pendiente", 10, False),
    ("paid", "Pagado", 20, False),
    ("preparing", "Preparando", 30, False),
    ("shipped", "Enviado", 40, False),
    ("delivered", "Entregado", 50, True),
    ("cancelled", "Cancelado", 90, True),
]

# Valores iniciales. Se editan desde el panel (tabla settings).
DEFAULT_SETTINGS = {
    "store": {
        "name": "Nombre de la tienda",
        "tagline": "Descripción corta de la tienda",
        # Mensaje de marca en la portada. Las *palabras entre asteriscos* se resaltan.
        "statement": None,
        # Frase de cierre gigante en el pie de página (si falta, se usa el nombre).
        "closing_line": None,
        "logo_url": None,
        "currency": "GTQ",
        "currency_symbol": "Q",
        "locale": "es-GT",
        "is_placeholder": True,
    },
    "theme": {"primary": "#1F3B4D", "accent": "#2F7D6D", "points": "#B8862B", "font": "deportiva"},
    "contact": {
        "email": None, "phone": None, "whatsapp": None, "address": None,
        "hours": None,
    },
    "social": {"facebook": None, "instagram": None, "tiktok": None},
    "loyalty": {
        "enabled": True,
        "points_per_currency_unit": 1,        # puntos por cada Q1 pagado
        "redeem_block_points": 1000,          # 1,000 puntos...
        "redeem_block_value_cents": 5000,     # ...= Q50 de descuento
        "max_points_discount_percent": 50,    # tope de descuento con puntos
        "earn_on_status": "delivered",        # los puntos pasan de pendientes a disponibles
        "program_name": "Programa de puntos",
    },
    "shipping": {
        "methods": [
            {"code": "pickup", "label": "Recoger en tienda", "price_cents": 0, "requires_address": False, "active": True},
            {"code": "standard", "label": "Envío a domicilio", "price_cents": 3000, "requires_address": True, "active": True},
        ],
        "free_shipping_over_cents": None,
    },
    "checkout": {"allow_notes": True},
    # Correos que reciben el aviso de cada pedido nuevo (separados por comas).
    "notifications": {"new_order_emails": None},
    "payments": {
        "bank_transfer_instructions": "La tienda te enviará los datos bancarios para completar la transferencia.",
    },
    "seo": {
        "default_title": "Tienda en línea",
        "default_description": "Compra en línea con envío a domicilio y programa de puntos.",
        "og_image": None,
    },
}


def _statements(sql: str) -> list[str]:
    lines = [ln for ln in sql.splitlines() if not ln.strip().startswith("--")]
    return [s.strip() for s in "\n".join(lines).split(";") if s.strip()]


def migrate(conn) -> list[str]:
    conn.execute(
        "CREATE TABLE IF NOT EXISTS schema_migrations (version VARCHAR(100) PRIMARY KEY, applied_at VARCHAR(40) NOT NULL)"
    )
    applied = {r["version"] for r in conn.all("SELECT version FROM schema_migrations")}
    done = []
    for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
        version = path.stem
        if version in applied:
            continue
        sql = path.read_text(encoding="utf-8")
        for token, value in DIALECT_TOKENS[conn.dialect].items():
            sql = sql.replace(token, value)
        with conn.transaction():
            for stmt in _statements(sql):
                conn.execute(stmt)
            conn.execute("INSERT INTO schema_migrations (version, applied_at) VALUES (?, ?)", (version, now_iso()))
        done.append(version)
    ensure_reference_data(conn)
    return done


def ensure_reference_data(conn) -> None:
    with conn.transaction():
        for code, desc in PERMISSIONS.items():
            if not conn.one("SELECT id FROM permissions WHERE code = ?", (code,)):
                conn.insert("INSERT INTO permissions (code, description) VALUES (?, ?)", (code, desc))
        for code, (name, is_staff, perms) in ROLES.items():
            role = conn.one("SELECT id FROM roles WHERE code = ?", (code,))
            if role:
                continue
            role_id = conn.insert(
                "INSERT INTO roles (code, name, is_staff, is_system) VALUES (?, ?, ?, ?)",
                (code, name, is_staff, True),
            )
            for perm in perms:
                pid = conn.scalar("SELECT id FROM permissions WHERE code = ?", (perm,))
                conn.execute("INSERT INTO role_permissions (role_id, permission_id) VALUES (?, ?)", (role_id, pid))
        # El administrador siempre tiene todos los permisos, incluidos los nuevos.
        admin_id = conn.scalar("SELECT id FROM roles WHERE code = 'admin'")
        for perm in PERMISSIONS:
            pid = conn.scalar("SELECT id FROM permissions WHERE code = ?", (perm,))
            if not conn.one("SELECT 1 AS x FROM role_permissions WHERE role_id = ? AND permission_id = ?", (admin_id, pid)):
                conn.execute("INSERT INTO role_permissions (role_id, permission_id) VALUES (?, ?)", (admin_id, pid))
        for code, label, order, final in ORDER_STATUSES:
            if not conn.one("SELECT code FROM order_statuses WHERE code = ?", (code,)):
                conn.execute(
                    "INSERT INTO order_statuses (code, label, sort_order, is_final) VALUES (?, ?, ?, ?)",
                    (code, label, order, final),
                )
        for key, value in DEFAULT_SETTINGS.items():
            if not conn.one("SELECT key FROM settings WHERE key = ?", (key,)):
                conn.execute(
                    "INSERT INTO settings (key, value, updated_at) VALUES (?, ?, ?)",
                    (key, json.dumps(value), now_iso()),
                )
