"""Catálogo público: búsqueda, filtros, orden, detalle y categorías."""
from __future__ import annotations

import threading
import time

from app.core.errors import NotFound
from app.core.jsonutil import load_json
from app.core.validation import search_normalize
from app.db import get_db
from app.services import promotion_service

SORTS = {
    "newest": "p.created_at DESC, p.id DESC",
    "price_asc": "p.price_cents ASC, p.id ASC",
    "price_desc": "p.price_cents DESC, p.id DESC",
    "best_selling": "p.sold_count DESC, p.id DESC",
    "name": "p.name ASC, p.id ASC",
}

LIST_COLUMNS = """p.id, p.name, p.slug, p.sku, p.short_description, p.price_cents, p.compare_at_cents,
    p.stock, p.low_stock_threshold, p.status, p.is_featured, p.is_demo, p.category_id, p.created_at,
    c.name AS category_name, c.slug AS category_slug,
    (SELECT url FROM product_images i WHERE i.product_id = p.id ORDER BY i.sort_order, i.id LIMIT 1) AS image_url,
    (SELECT alt FROM product_images i WHERE i.product_id = p.id ORDER BY i.sort_order, i.id LIMIT 1) AS image_alt"""

# --------------------------------------------------------------- categorías
_cat_cache = {"at": 0.0, "rows": None}
_cat_lock = threading.Lock()
CAT_TTL = 60


def all_categories(include_inactive: bool = False) -> list[dict]:
    with _cat_lock:
        cached = _cat_cache["rows"] if time.time() - _cat_cache["at"] < CAT_TTL else None
    if cached is None:
        cached = get_db().all(
            """SELECT c.id, c.parent_id, c.name, c.slug, c.description, c.image_url, c.sort_order, c.is_active,
                      c.seo_title, c.seo_description,
                      (SELECT COUNT(*) FROM products p WHERE p.category_id = c.id AND p.status = 'active') AS product_count
               FROM categories c ORDER BY c.sort_order, c.name"""
        )
        for c in cached:
            c["is_active"] = bool(c["is_active"])
        with _cat_lock:
            _cat_cache.update(at=time.time(), rows=cached)
    return [dict(c) for c in cached if include_inactive or c["is_active"]]


def invalidate_categories() -> None:
    with _cat_lock:
        _cat_cache.update(at=0.0, rows=None)


def category_tree() -> list[dict]:
    cats = all_categories()
    by_parent: dict = {}
    for c in cats:
        by_parent.setdefault(c["parent_id"], []).append(c)
    ids = {c["id"] for c in cats}

    def build(parent):
        out = []
        for c in by_parent.get(parent, []):
            node = dict(c)
            node["children"] = build(c["id"])
            node["total_count"] = node["product_count"] + sum(ch["total_count"] for ch in node["children"])
            out.append(node)
        return out

    roots = [c for c in cats if c["parent_id"] is None or c["parent_id"] not in ids]
    tree = []
    for r in roots:
        node = dict(r)
        node["children"] = build(r["id"])
        node["total_count"] = node["product_count"] + sum(ch["total_count"] for ch in node["children"])
        tree.append(node)
    return tree


def descendant_ids(category_id: int) -> list[int]:
    cats = all_categories(include_inactive=True)
    result, frontier = [category_id], [category_id]
    while frontier:
        frontier = [c["id"] for c in cats if c["parent_id"] in frontier]
        result.extend(frontier)
    return result


def ancestor_ids(category_id: int | None) -> set[int]:
    cats = {c["id"]: c for c in all_categories(include_inactive=True)}
    out, cur = set(), category_id
    while cur and cur in cats and cur not in out:
        out.add(cur)
        cur = cats[cur]["parent_id"]
    return out


def category_by_slug(slug: str) -> dict:
    for c in all_categories():
        if c["slug"] == slug:
            return c
    raise NotFound("Categoría no encontrada.")


def breadcrumb(category_id: int | None) -> list[dict]:
    cats = {c["id"]: c for c in all_categories(include_inactive=True)}
    chain, cur, seen = [], category_id, set()
    while cur and cur in cats and cur not in seen:
        seen.add(cur)
        chain.append({"name": cats[cur]["name"], "slug": cats[cur]["slug"]})
        cur = cats[cur]["parent_id"]
    return list(reversed(chain))


# --------------------------------------------------------------- productos
def availability(stock: int, threshold: int) -> str:
    if stock <= 0:
        return "out_of_stock"
    if stock <= threshold:
        return "low_stock"
    return "in_stock"


def serialize_card(row: dict, promotions=None) -> dict:
    row = dict(row)
    row["_category_ids"] = ancestor_ids(row.get("category_id"))
    discount, promo = promotion_service.unit_discount(row, promotions)
    price = row["price_cents"] - discount
    compare = row["compare_at_cents"] if row["compare_at_cents"] and row["compare_at_cents"] > price else None
    if discount and not compare:
        compare = row["price_cents"]
    return {
        "id": row["id"],
        "name": row["name"],
        "slug": row["slug"],
        "sku": row["sku"],
        "short_description": row.get("short_description"),
        "price_cents": price,
        "compare_at_cents": compare,
        "promotion": promo["name"] if promo else None,
        "stock": row["stock"],
        "availability": availability(row["stock"], row.get("low_stock_threshold", 5)),
        "is_featured": bool(row.get("is_featured")),
        "is_demo": bool(row.get("is_demo")),
        "category": {"name": row.get("category_name"), "slug": row.get("category_slug")} if row.get("category_slug") else None,
        "image": {"url": row.get("image_url"), "alt": row.get("image_alt") or row["name"]} if row.get("image_url") else None,
        "created_at": row.get("created_at"),
    }


def list_products(params: dict, page: int, size: int) -> tuple[list[dict], int]:
    where = ["p.status = 'active'"]
    args: list = []
    q = search_normalize(params.get("q") or "")[:100]
    if q:
        for word in q.split(" ")[:6]:
            where.append("p.search_text LIKE ?")
            args.append(f"%{word}%")
    if params.get("category"):
        cat = category_by_slug(params["category"])
        ids = descendant_ids(cat["id"])
        where.append(f"p.category_id IN ({','.join('?' * len(ids))})")
        args.extend(ids)
    if params.get("tag"):
        where.append("EXISTS (SELECT 1 FROM product_tags pt JOIN tags t ON t.id = pt.tag_id WHERE pt.product_id = p.id AND t.slug = ?)")
        args.append(params["tag"])
    for key, op in (("min_price", ">="), ("max_price", "<=")):
        value = params.get(key)
        if value not in (None, ""):
            try:
                where.append(f"p.price_cents {op} ?")
                args.append(int(value))
            except ValueError:
                pass
    if params.get("in_stock") in ("1", "true"):
        where.append("p.stock > 0")
    if params.get("featured") in ("1", "true"):
        where.append("p.is_featured = TRUE")
    if params.get("on_sale") in ("1", "true"):
        where.append("p.compare_at_cents IS NOT NULL AND p.compare_at_cents > p.price_cents")
    order = SORTS.get(params.get("sort") or "newest", SORTS["newest"])
    where_sql = " AND ".join(where)
    db = get_db()
    total = db.scalar(f"SELECT COUNT(*) AS n FROM products p WHERE {where_sql}", args)
    rows = db.all(
        f"""SELECT {LIST_COLUMNS} FROM products p LEFT JOIN categories c ON c.id = p.category_id
            WHERE {where_sql} ORDER BY {order} LIMIT ? OFFSET ?""",
        [*args, size, (page - 1) * size],
    )
    promos = promotion_service.active_promotions()
    return [serialize_card(r, promos) for r in rows], total


def cards_by_ids(ids: list[int]) -> list[dict]:
    if not ids:
        return []
    rows = get_db().all(
        f"""SELECT {LIST_COLUMNS} FROM products p LEFT JOIN categories c ON c.id = p.category_id
            WHERE p.status = 'active' AND p.id IN ({','.join('?' * len(ids))})""",
        ids,
    )
    promos = promotion_service.active_promotions()
    by_id = {r["id"]: serialize_card(r, promos) for r in rows}
    return [by_id[i] for i in ids if i in by_id]


def get_product(slug: str, include_inactive: bool = False) -> dict:
    db = get_db()
    row = db.one(
        f"""SELECT {LIST_COLUMNS}, p.description, p.attributes, p.seo_title, p.seo_description, p.updated_at
            FROM products p LEFT JOIN categories c ON c.id = p.category_id WHERE p.slug = ?""",
        (slug,),
    )
    if not row or (row["status"] != "active" and not include_inactive):
        raise NotFound("Este producto no existe o ya no está disponible.")
    product = serialize_card(row)
    product.update(
        description=row["description"],
        attributes=load_json(row["attributes"], {}) or {},
        seo_title=row["seo_title"] or row["name"],
        seo_description=row["seo_description"] or (row["short_description"] or "")[:160],
        updated_at=row["updated_at"],
        breadcrumb=breadcrumb(row["category_id"]),
        images=db.all("SELECT url, alt FROM product_images WHERE product_id = ? ORDER BY sort_order, id", (row["id"],)),
        tags=db.all("SELECT t.name, t.slug FROM tags t JOIN product_tags pt ON pt.tag_id = t.id WHERE pt.product_id = ? ORDER BY t.name", (row["id"],)),
    )
    product["related"] = related_products(row["id"], row["category_id"])
    return product


def related_products(product_id: int, category_id: int | None, limit: int = 4) -> list[dict]:
    db = get_db()
    ids = [r["related_id"] for r in db.all("SELECT related_id FROM product_related WHERE product_id = ?", (product_id,))]
    if len(ids) < limit and category_id:
        extra = db.all(
            """SELECT id FROM products WHERE category_id = ? AND id <> ? AND status = 'active'
               ORDER BY sold_count DESC, id DESC LIMIT ?""",
            (category_id, product_id, limit * 2),
        )
        ids += [r["id"] for r in extra if r["id"] not in ids]
    return cards_by_ids(ids[:limit])


def suggest(q: str, limit: int = 6) -> list[dict]:
    q = search_normalize(q)[:60]
    if len(q) < 2:
        return []
    rows = get_db().all(
        """SELECT name, slug FROM products WHERE status = 'active' AND search_text LIKE ?
           ORDER BY sold_count DESC LIMIT ?""",
        (f"%{q}%", limit),
    )
    return rows
