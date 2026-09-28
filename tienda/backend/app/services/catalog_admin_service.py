"""Gestión del catálogo desde el panel."""
from __future__ import annotations

from app.core.errors import Conflict, NotFound, ValidationError
from app.core.jsonutil import dump_json, load_json
from app.core.timeutil import now_iso
from app.core.validation import V, search_normalize, slugify
from app.db import IntegrityError, get_db
from app.services import catalog_service

STATUSES = {"draft", "active", "archived"}


def _unique_slug(db, table: str, base: str, exclude_id: int | None = None) -> str:
    slug, n = base, 2
    while db.one(f"SELECT id FROM {table} WHERE slug = ? AND id <> ?", (slug, exclude_id or 0)):
        slug = f"{base}-{n}"
        n += 1
    return slug


def _search_text(name, sku, short, tags, category_name) -> str:
    return search_normalize(" ".join(filter(None, [name, sku, short, " ".join(tags), category_name])))


def validate_product(data: dict) -> dict:
    v = (V(data)
         .str("name", max_len=200).str("sku", max_len=64).str("slug", required=False, max_len=220)
         .str("short_description", required=False, max_len=300).str("description", required=False, max_len=20000)
         .int("price_cents", min_value=0, max_value=10**10)
         .int("compare_at_cents", required=False, min_value=0, max_value=10**10)
         .int("stock", required=False, min_value=0, max_value=10**7, default=0)
         .int("low_stock_threshold", required=False, min_value=0, max_value=10**6, default=5)
         .int("category_id", required=False)
         .choice("status", STATUSES, required=False, default="draft")
         .bool("is_featured")
         .str("seo_title", required=False, max_len=70).str("seo_description", required=False, max_len=170))
    out = v.check()
    out["sku"] = out["sku"].upper()
    tags = data.get("tags") or []
    if not isinstance(tags, list) or not all(isinstance(t, str) for t in tags):
        raise ValidationError("Las etiquetas deben ser una lista de textos.")
    out["tags"] = [t.strip()[:60] for t in tags if t.strip()][:20]
    images = data.get("images") or []
    if not isinstance(images, list):
        raise ValidationError("Las imágenes deben ser una lista.")
    clean_images = []
    for img in images[:12]:
        url = (img.get("url") if isinstance(img, dict) else None) or ""
        if not (url.startswith("/uploads/") or url.startswith("https://") or url.startswith("/assets/")):
            raise ValidationError("URL de imagen no permitida.", details={"images": url[:80]})
        clean_images.append({"url": url[:500], "alt": (img.get("alt") or "")[:200]})
    out["images"] = clean_images
    related = data.get("related_ids") or []
    out["related_ids"] = [int(r) for r in related if str(r).isdigit()][:12]
    attrs = data.get("attributes") or {}
    if not isinstance(attrs, dict) or len(attrs) > 30:
        raise ValidationError("Atributos no válidos.")
    out["attributes"] = {str(k)[:60]: str(v)[:300] for k, v in attrs.items()}
    return out


def save_product(data: dict, product_id: int | None, user_id: int) -> dict:
    p = validate_product(data)
    db = get_db()
    try:
        with db.transaction():
            if p["category_id"] and not db.one("SELECT id FROM categories WHERE id = ?", (p["category_id"],)):
                raise ValidationError("La categoría no existe.", details={"category_id": "No existe."})
            slug = _unique_slug(db, "products", slugify(p.get("slug") or p["name"]), product_id)
            cat_name = db.scalar("SELECT name FROM categories WHERE id = ?", (p["category_id"],)) if p["category_id"] else None
            search = _search_text(p["name"], p["sku"], p.get("short_description"), p["tags"], cat_name)
            cols = ("category_id", "name", "slug", "sku", "short_description", "description", "price_cents",
                    "compare_at_cents", "low_stock_threshold", "status", "is_featured", "attributes", "search_text",
                    "seo_title", "seo_description")
            vals = (p["category_id"], p["name"], slug, p["sku"], p.get("short_description"), p.get("description"),
                    p["price_cents"], p.get("compare_at_cents"), p["low_stock_threshold"], p["status"], p["is_featured"],
                    dump_json(p["attributes"]), search, p.get("seo_title"), p.get("seo_description"))
            if product_id:
                before = db.one("SELECT stock FROM products WHERE id = ?", (product_id,))
                if not before:
                    raise NotFound("Producto no encontrado.")
                db.execute(f"UPDATE products SET {', '.join(c + ' = ?' for c in cols)}, updated_at = ? WHERE id = ?",
                           (*vals, now_iso(), product_id))
                if "stock" in data and data["stock"] is not None and p["stock"] != before["stock"]:
                    set_stock(db, product_id, p["stock"], user_id, "adjustment")
            else:
                product_id = db.insert(
                    f"INSERT INTO products ({', '.join(cols)}, stock, created_at, updated_at) VALUES ({', '.join('?' * len(cols))}, ?, ?, ?)",
                    (*vals, p["stock"], now_iso(), now_iso()),
                )
                if p["stock"]:
                    db.insert("INSERT INTO inventory_movements (product_id, delta, reason, user_id, created_at) VALUES (?, ?, 'initial', ?, ?)",
                              (product_id, p["stock"], user_id, now_iso()))
            _set_tags(db, product_id, p["tags"])
            db.execute("DELETE FROM product_images WHERE product_id = ?", (product_id,))
            for i, img in enumerate(p["images"]):
                db.insert("INSERT INTO product_images (product_id, url, alt, sort_order) VALUES (?, ?, ?, ?)",
                          (product_id, img["url"], img["alt"], i))
            db.execute("DELETE FROM product_related WHERE product_id = ?", (product_id,))
            for rid in p["related_ids"]:
                if rid != product_id and db.one("SELECT id FROM products WHERE id = ?", (rid,)):
                    db.execute("INSERT INTO product_related (product_id, related_id) VALUES (?, ?)", (product_id, rid))
    except IntegrityError:
        raise Conflict("Ya existe un producto con ese SKU.", details={"sku": "Duplicado."})
    catalog_service.invalidate_categories()
    return get_product_admin(product_id)


def _set_tags(db, product_id, tags):
    db.execute("DELETE FROM product_tags WHERE product_id = ?", (product_id,))
    for name in dict.fromkeys(tags):
        slug = slugify(name)
        tag = db.one("SELECT id FROM tags WHERE slug = ?", (slug,))
        tag_id = tag["id"] if tag else db.insert("INSERT INTO tags (name, slug) VALUES (?, ?)", (name, slug))
        db.execute("INSERT INTO product_tags (product_id, tag_id) VALUES (?, ?)", (product_id, tag_id))


def set_stock(db, product_id: int, new_stock: int, user_id: int, reason: str = "adjustment") -> None:
    row = db.one("SELECT stock FROM products WHERE id = ?", (product_id,))
    if not row:
        raise NotFound("Producto no encontrado.")
    delta = new_stock - row["stock"]
    # Condicionado al valor leído: si una venta ocurrió entre medio, se reintenta desde el panel.
    if not db.execute("UPDATE products SET stock = ?, updated_at = ? WHERE id = ? AND stock = ?",
                      (new_stock, now_iso(), product_id, row["stock"])):
        raise Conflict("El stock cambió mientras editabas (probablemente por una venta). Recarga e inténtalo de nuevo.")
    db.insert("INSERT INTO inventory_movements (product_id, delta, reason, user_id, created_at) VALUES (?, ?, ?, ?, ?)",
              (product_id, delta, reason, user_id, now_iso()))


def adjust_stock(product_id: int, delta: int, user_id: int, reason: str) -> int:
    db = get_db()
    with db.transaction():
        ok = db.execute("UPDATE products SET stock = stock + ?, updated_at = ? WHERE id = ? AND stock + ? >= 0",
                        (delta, now_iso(), product_id, delta))
        if not ok:
            raise Conflict("El ajuste dejaría el stock en negativo o el producto no existe.")
        db.insert("INSERT INTO inventory_movements (product_id, delta, reason, user_id, created_at) VALUES (?, ?, ?, ?, ?)",
                  (product_id, delta, reason[:30], user_id, now_iso()))
        return db.scalar("SELECT stock FROM products WHERE id = ?", (product_id,))


def get_product_admin(product_id: int) -> dict:
    db = get_db()
    p = db.one("SELECT * FROM products WHERE id = ?", (product_id,))
    if not p:
        raise NotFound("Producto no encontrado.")
    p["is_featured"] = bool(p["is_featured"])
    p["is_demo"] = bool(p["is_demo"])
    p["attributes"] = load_json(p["attributes"], {}) or {}
    p.pop("search_text", None)
    p["images"] = db.all("SELECT url, alt FROM product_images WHERE product_id = ? ORDER BY sort_order, id", (product_id,))
    p["tags"] = [r["name"] for r in db.all("SELECT t.name FROM tags t JOIN product_tags pt ON pt.tag_id = t.id WHERE pt.product_id = ?", (product_id,))]
    p["related_ids"] = [r["related_id"] for r in db.all("SELECT related_id FROM product_related WHERE product_id = ?", (product_id,))]
    return p


def list_products_admin(q: str, status: str | None, category_id: int | None, low_stock: bool, page: int, size: int):
    where, args = ["1=1"], []
    if q:
        where.append("p.search_text LIKE ?")
        args.append(f"%{search_normalize(q)[:100]}%")
    if status in STATUSES:
        where.append("p.status = ?")
        args.append(status)
    if category_id:
        where.append("p.category_id = ?")
        args.append(category_id)
    if low_stock:
        where.append("p.stock <= p.low_stock_threshold")
    w = " AND ".join(where)
    db = get_db()
    total = db.scalar(f"SELECT COUNT(*) AS n FROM products p WHERE {w}", args)
    rows = db.all(
        f"""SELECT p.id, p.name, p.slug, p.sku, p.price_cents, p.compare_at_cents, p.stock, p.low_stock_threshold, p.status,
                   p.is_featured, p.is_demo, p.sold_count, p.updated_at, c.name AS category_name,
                   (SELECT url FROM product_images i WHERE i.product_id = p.id ORDER BY i.sort_order, i.id LIMIT 1) AS image_url
            FROM products p LEFT JOIN categories c ON c.id = p.category_id WHERE {w}
            ORDER BY p.updated_at DESC, p.id DESC LIMIT ? OFFSET ?""",
        [*args, size, (page - 1) * size],
    )
    for r in rows:
        r["is_featured"], r["is_demo"] = bool(r["is_featured"]), bool(r["is_demo"])
    return rows, total


def delete_product(product_id: int) -> str:
    """Si el producto tiene ventas se archiva (para conservar el historial);
    si no, se elimina."""
    db = get_db()
    with db.transaction():
        if not db.one("SELECT id FROM products WHERE id = ?", (product_id,)):
            raise NotFound("Producto no encontrado.")
        if db.one("SELECT id FROM order_items WHERE product_id = ? LIMIT 1", (product_id,)):
            db.execute("UPDATE products SET status = 'archived', updated_at = ? WHERE id = ?", (now_iso(), product_id))
            return "archived"
        db.execute("DELETE FROM products WHERE id = ?", (product_id,))
        return "deleted"


# ---------------------------------------------------------------- categorías
def save_category(data: dict, category_id: int | None) -> dict:
    out = (V(data).str("name", max_len=120).str("slug", required=False, max_len=140)
           .str("description", required=False, max_len=2000).int("parent_id", required=False)
           .int("sort_order", required=False, default=0).bool("is_active", default=True)
           .str("image_url", required=False, max_len=500)
           .str("seo_title", required=False, max_len=70).str("seo_description", required=False, max_len=170)).check()
    db = get_db()
    with db.transaction():
        if out["parent_id"]:
            if out["parent_id"] == category_id:
                raise ValidationError("Una categoría no puede ser su propia madre.")
            if category_id and out["parent_id"] in catalog_service.descendant_ids(category_id):
                raise ValidationError("No puedes mover una categoría dentro de sus subcategorías.")
            if not db.one("SELECT id FROM categories WHERE id = ?", (out["parent_id"],)):
                raise ValidationError("La categoría superior no existe.")
        slug = _unique_slug(db, "categories", slugify(out.get("slug") or out["name"]), category_id)
        cols = ("parent_id", "name", "slug", "description", "image_url", "sort_order", "is_active", "seo_title", "seo_description")
        vals = (out["parent_id"], out["name"], slug, out.get("description"), out.get("image_url"), out["sort_order"],
                out["is_active"], out.get("seo_title"), out.get("seo_description"))
        if category_id:
            if not db.execute(f"UPDATE categories SET {', '.join(c + ' = ?' for c in cols)}, updated_at = ? WHERE id = ?",
                              (*vals, now_iso(), category_id)):
                raise NotFound("Categoría no encontrada.")
        else:
            category_id = db.insert(
                f"INSERT INTO categories ({', '.join(cols)}, created_at, updated_at) VALUES ({', '.join('?' * len(cols))}, ?, ?)",
                (*vals, now_iso(), now_iso()),
            )
    catalog_service.invalidate_categories()
    return db.one("SELECT * FROM categories WHERE id = ?", (category_id,))


def delete_category(category_id: int) -> None:
    db = get_db()
    with db.transaction():
        if db.one("SELECT id FROM products WHERE category_id = ? LIMIT 1", (category_id,)):
            raise Conflict("La categoría tiene productos. Muévelos a otra categoría antes de eliminarla.")
        if db.one("SELECT id FROM categories WHERE parent_id = ? LIMIT 1", (category_id,)):
            raise Conflict("La categoría tiene subcategorías. Elimínalas o muévelas primero.")
        if not db.execute("DELETE FROM categories WHERE id = ?", (category_id,)):
            raise NotFound("Categoría no encontrada.")
    catalog_service.invalidate_categories()
