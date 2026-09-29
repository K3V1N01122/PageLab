"""Datos de DEMOSTRACIÓN para probar la tienda.

Todo lo que se crea aquí está marcado:
- productos con `is_demo = TRUE`, SKU con prefijo DEMO- y "(demo)" en el nombre;
- categorías con "(demo)";
- usuarios con correos @example.com (dominio reservado, nunca real).
Los productos demo no aparecen en el sitemap y se marcan `noindex`.
Para eliminarlos: `DELETE FROM products WHERE is_demo = TRUE` (ver README).
"""
from __future__ import annotations

import colorsys
import os
import random
import re

from flask import current_app

from app.core.timeutil import iso_in, now_iso
from app.core.validation import search_normalize, slugify
from app.services import user_service

CATEGORIES = [
    ("Hogar (demo)", None, "Artículos de prueba para el hogar."),
    ("Cocina (demo)", "Hogar (demo)", "Subcategoría de prueba."),
    ("Decoración (demo)", "Hogar (demo)", "Subcategoría de prueba."),
    ("Accesorios (demo)", None, "Accesorios de prueba."),
    ("Tecnología (demo)", None, "Productos tecnológicos de prueba."),
    ("Cuidado personal (demo)", None, "Productos de cuidado personal de prueba."),
]

PRODUCTS = [
    # nombre, categoría, precio, precio anterior, stock, destacado, etiquetas
    ("Botella térmica 750 ml", "Cocina (demo)", 18900, None, 40, True, ["acero", "viaje"]),
    ("Juego de tazas de cerámica", "Cocina (demo)", 24500, 29900, 12, False, ["ceramica"]),
    ("Tabla de cortar de bambú", "Cocina (demo)", 15900, None, 3, False, ["bambu"]),
    ("Lámpara de mesa lineal", "Decoración (demo)", 42000, None, 8, True, ["iluminacion"]),
    ("Maceta de barro mediana", "Decoración (demo)", 9500, 12000, 25, False, ["plantas"]),
    ("Cojín tejido a mano", "Decoración (demo)", 13500, None, 0, False, ["textil"]),
    ("Mochila urbana 20 L", "Accesorios (demo)", 38900, 45000, 15, True, ["viaje", "urbano"]),
    ("Billetera de cuero", "Accesorios (demo)", 21000, None, 30, False, ["cuero"]),
    ("Gorra clásica", "Accesorios (demo)", 12500, None, 50, False, ["urbano"]),
    ("Audífonos inalámbricos", "Tecnología (demo)", 69900, 79900, 10, True, ["audio"]),
    ("Cargador rápido USB-C", "Tecnología (demo)", 17900, None, 60, False, ["carga"]),
    ("Soporte para laptop", "Tecnología (demo)", 27500, None, 4, False, ["oficina"]),
    ("Jabón artesanal de avena", "Cuidado personal (demo)", 4500, None, 80, False, ["natural"]),
    ("Kit de cuidado facial", "Cuidado personal (demo)", 32000, 36000, 9, True, ["natural", "regalo"]),
    ("Toalla de algodón", "Cuidado personal (demo)", 11900, None, 22, False, ["textil"]),
    ("Set de velas aromáticas", "Decoración (demo)", 16500, None, 18, False, ["regalo"]),
]

DESCRIPTION = ("Este es un producto de prueba creado para validar el catálogo, el carrito, el checkout y el sistema de puntos. "
               "Reemplázalo por un producto real desde el panel de administración.")


def _placeholder(name: str, index: int, variant: int) -> str:
    """Genera una imagen abstracta rotulada 'Imagen de prueba'."""
    from PIL import Image, ImageDraw
    folder = current_app.config["UPLOAD_DIR"] / "demo"
    folder.mkdir(parents=True, exist_ok=True)
    fname = f"demo-{index:02d}-{variant}.webp"
    path = folder / fname
    if not path.exists():
        rnd = random.Random(index * 10 + variant)
        hue = (index * 0.13 + variant * 0.05) % 1
        bg = tuple(int(c * 255) for c in colorsys.hls_to_rgb(hue, 0.90, 0.28))
        fg = tuple(int(c * 255) for c in colorsys.hls_to_rgb(hue, 0.45, 0.35))
        img = Image.new("RGB", (900, 900), bg)
        d = ImageDraw.Draw(img)
        shape = (index + variant) % 3
        cx, cy, r = 450 + rnd.randint(-60, 60), 420 + rnd.randint(-40, 40), rnd.randint(170, 230)
        if shape == 0:
            d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=fg)
        elif shape == 1:
            d.rounded_rectangle([cx - r, cy - int(r * 1.2), cx + r, cy + int(r * 1.2)], radius=40, fill=fg)
        else:
            d.polygon([(cx, cy - r), (cx + r, cy + r), (cx - r, cy + r)], fill=fg)
        d.rectangle([0, 820, 900, 900], fill=(255, 255, 255))
        d.text((32, 845), "Imagen de prueba", fill=(90, 90, 90))
        img.save(path, "WEBP", quality=80)
    return f"{current_app.config['UPLOAD_URL_PREFIX']}/demo/{fname}"


def restore_demo_images(db) -> int:
    """Vuelve a generar las imágenes demo que falten.

    En hostings gratuitos (p. ej. Render) el disco se borra en cada reinicio,
    así que las imágenes demo se recrean al arrancar. Las imágenes que suba el
    administrador en ese tipo de hosting también se pierden al reiniciar.
    """
    restored = 0
    prefix = f"{current_app.config['UPLOAD_URL_PREFIX']}/demo/"
    for row in db.all("SELECT url FROM product_images WHERE url LIKE ?", (f"{prefix}demo-%",)):
        m = re.search(r"demo-(\d+)-(\d+)\.webp$", row["url"])
        if m and not (current_app.config["UPLOAD_DIR"] / "demo" / m.group(0)).exists():
            _placeholder("", int(m.group(1)), int(m.group(2)))
            restored += 1
    return restored


def seed(db) -> str:
    if db.one("SELECT id FROM products WHERE is_demo = TRUE LIMIT 1"):
        restored = restore_demo_images(db)
        return "Los datos de demostración ya existen." + (f" Se regeneraron {restored} imágenes." if restored else "")
    with db.transaction():
        cat_ids = {}
        for i, (name, parent, desc) in enumerate(CATEGORIES):
            cat_ids[name] = db.insert(
                """INSERT INTO categories (parent_id, name, slug, description, sort_order, is_active, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, TRUE, ?, ?)""",
                (cat_ids.get(parent), name, slugify(name), desc, i, now_iso(), now_iso()),
            )
        product_ids = []
        for i, (name, cat, price, compare, stock, featured, tags) in enumerate(PRODUCTS, start=1):
            full = f"{name} (demo)"
            sku = f"DEMO-{i:03d}"
            created = iso_in(days=-(len(PRODUCTS) - i) * 3)
            pid = db.insert(
                """INSERT INTO products (category_id, name, slug, sku, short_description, description, price_cents,
                       compare_at_cents, stock, status, is_featured, is_demo, attributes, search_text, sold_count,
                       created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', ?, TRUE, ?, ?, ?, ?, ?)""",
                (cat_ids[cat], full, slugify(full), sku, "Producto de prueba. Reemplázalo por uno real.", DESCRIPTION,
                 price, compare, stock, featured, '{"Material": "Dato de prueba", "Garantía": "Dato de prueba"}',
                 search_normalize(f"{full} {sku} {' '.join(tags)} {cat}"), random.Random(i).randint(0, 40), created, created),
            )
            product_ids.append(pid)
            for v in range(3 if i % 3 == 0 else 2):
                db.insert("INSERT INTO product_images (product_id, url, alt, sort_order) VALUES (?, ?, ?, ?)",
                          (pid, _placeholder(name, i, v), f"{full}: imagen de prueba {v + 1}", v))
            for t in tags:
                tag = db.one("SELECT id FROM tags WHERE slug = ?", (slugify(t),))
                tid = tag["id"] if tag else db.insert("INSERT INTO tags (name, slug) VALUES (?, ?)", (t, slugify(t)))
                db.execute("INSERT INTO product_tags (product_id, tag_id) VALUES (?, ?)", (pid, tid))
            if stock:
                db.insert("INSERT INTO inventory_movements (product_id, delta, reason, created_at) VALUES (?, ?, 'initial', ?)",
                          (pid, stock, now_iso()))

        db.execute("INSERT INTO product_related (product_id, related_id) VALUES (?, ?)", (product_ids[0], product_ids[6]))
        rewards = [
            ("Q50 de descuento", "Cupón de Q50 para tu próxima compra.", "fixed_discount", 1000, 5000, 0),
            ("Envío gratis", "Tu próximo envío a domicilio sin costo.", "free_shipping", 400, 0, 0),
            ("10% de descuento", "Cupón del 10% sobre el subtotal.", "percent_discount", 1500, 0, 10),
        ]
        for name, desc, kind, cost, value, pct in rewards:
            db.insert(
                """INSERT INTO rewards (name, description, kind, points_cost, value_cents, percent, coupon_valid_days,
                                        is_active, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, 30, TRUE, ?, ?)""",
                (name, desc, kind, cost, value, pct, now_iso(), now_iso()),
            )
        db.insert(
            """INSERT INTO coupons (code, description, kind, percent, min_subtotal_cents, max_uses, per_user_limit, source,
                                    is_active, created_at, updated_at) VALUES ('DEMO10', 'Cupón de prueba: 10%', 'percent', 10, 10000, 1000, 1, 'admin', TRUE, ?, ?)""",
            (now_iso(), now_iso()),
        )
        db.insert(
            """INSERT INTO promotions (name, description, kind, value, target, target_id, is_active, created_at, updated_at)
               VALUES ('Promoción de prueba: 15% en Tecnología', 'Promoción automática de ejemplo', 'percent', 15, 'category', ?, TRUE, ?, ?)""",
            (cat_ids["Tecnología (demo)"], now_iso(), now_iso()),
        )

    # En una demo publicada, define DEMO_ADMIN_PASSWORD para que nadie más entre al panel.
    admin_password = os.getenv("DEMO_ADMIN_PASSWORD") or "AdminDemo123"
    admin = user_service.register({"email": "admin.demo@example.com", "password": admin_password, "first_name": "Admin",
                                   "last_name": "Demo", "phone": None}, role_code="admin")
    customer = user_service.register({"email": "cliente.demo@example.com", "password": "ClienteDemo123",
                                      "first_name": "Cliente", "last_name": "Demo", "phone": "+502 5555 0000"})
    from app.services import loyalty_service
    loyalty_service.admin_adjust(customer["id"], 1500, "Saldo inicial de prueba", admin["id"])
    return ("Datos de demostración cargados.\n"
            f"  Admin demo:   admin.demo@example.com / {'(DEMO_ADMIN_PASSWORD)' if os.getenv('DEMO_ADMIN_PASSWORD') else 'AdminDemo123'}\n"
            "  Cliente demo: cliente.demo@example.com / ClienteDemo123  (1,500 puntos de prueba)\n"
            "  Cupón demo:   DEMO10 (10% desde Q100)")
