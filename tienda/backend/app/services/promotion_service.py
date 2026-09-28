"""Promociones automáticas (descuento por producto, categoría o toda la tienda)."""
import threading
import time

from app.core.money import pct_of
from app.core.timeutil import now_iso
from app.db import get_db

CACHE_TTL = 30
_cache = {"at": 0.0, "rows": None}
_lock = threading.Lock()


def active_promotions() -> list[dict]:
    with _lock:
        if _cache["rows"] is not None and time.time() - _cache["at"] < CACHE_TTL:
            return _cache["rows"]
    ts = now_iso()
    rows = get_db().all(
        """SELECT id, name, kind, value, target, target_id FROM promotions
           WHERE is_active = TRUE AND (starts_at IS NULL OR starts_at <= ?) AND (ends_at IS NULL OR ends_at >= ?)""",
        (ts, ts),
    )
    with _lock:
        _cache.update(at=time.time(), rows=rows)
    return rows


def invalidate() -> None:
    with _lock:
        _cache.update(at=0.0, rows=None)


def unit_discount(product: dict, promotions: list[dict] | None = None) -> tuple[int, dict | None]:
    """Mejor descuento unitario aplicable (no acumulable) y la promoción usada."""
    promotions = active_promotions() if promotions is None else promotions
    best, best_promo = 0, None
    price = product["price_cents"]
    for p in promotions:
        applies = (
            p["target"] == "all"
            or (p["target"] == "product" and p["target_id"] == product["id"])
            or (p["target"] == "category" and p["target_id"] in product.get("_category_ids", {product.get("category_id")}))
        )
        if not applies:
            continue
        amount = pct_of(price, p["value"]) if p["kind"] == "percent" else p["value"]
        amount = min(amount, price)
        if amount > best:
            best, best_promo = amount, p
    return best, best_promo
