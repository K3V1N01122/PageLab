"""Administración de cupones, promociones y recompensas."""
from __future__ import annotations

from app.core.errors import Conflict, NotFound, ValidationError
from app.core.timeutil import now_iso, parse
from app.core.validation import V
from app.db import IntegrityError, get_db
from app.services import promotion_service, reward_service
from app.services.coupon_service import KINDS as COUPON_KINDS


def _dates(out: dict) -> dict:
    for k in ("starts_at", "ends_at"):
        if out.get(k):
            try:
                out[k] = parse(out[k]).isoformat()
            except ValueError:
                raise ValidationError("Fecha no válida.", details={k: "Usa el formato AAAA-MM-DD."})
    if out.get("starts_at") and out.get("ends_at") and out["ends_at"] < out["starts_at"]:
        raise ValidationError("La fecha final debe ser posterior a la inicial.", details={"ends_at": "Revisa las fechas."})
    return out


def _save(table: str, cols: tuple, out: dict, entity_id: int | None) -> dict:
    db = get_db()
    vals = tuple(out.get(c) for c in cols)
    try:
        with db.transaction():
            if entity_id:
                if not db.execute(f"UPDATE {table} SET {', '.join(c + ' = ?' for c in cols)}, updated_at = ? WHERE id = ?",
                                  (*vals, now_iso(), entity_id)):
                    raise NotFound("Registro no encontrado.")
            else:
                entity_id = db.insert(
                    f"INSERT INTO {table} ({', '.join(cols)}, created_at, updated_at) VALUES ({', '.join('?' * len(cols))}, ?, ?)",
                    (*vals, now_iso(), now_iso()),
                )
    except IntegrityError:
        raise Conflict("Ya existe un registro con ese código.", details={"code": "Duplicado."})
    return db.one(f"SELECT * FROM {table} WHERE id = ?", (entity_id,))


# ---------------------------------------------------------------- cupones
COUPON_COLS = ("code", "description", "kind", "value_cents", "percent", "product_id", "min_subtotal_cents",
               "starts_at", "ends_at", "max_uses", "per_user_limit", "is_active")


def save_coupon(data: dict, coupon_id: int | None) -> dict:
    out = (V(data).str("code", min_len=3, max_len=40).str("description", required=False, max_len=200)
           .choice("kind", COUPON_KINDS).int("value_cents", required=False, min_value=0, default=0)
           .int("percent", required=False, min_value=0, max_value=100, default=0).int("product_id", required=False)
           .int("min_subtotal_cents", required=False, min_value=0, default=0)
           .str("starts_at", required=False).str("ends_at", required=False)
           .int("max_uses", required=False, min_value=1).int("per_user_limit", required=False, min_value=0, default=1)
           .bool("is_active", default=True)).check()
    out["code"] = out["code"].upper().replace(" ", "")
    if out["kind"] == "fixed" and not out["value_cents"]:
        raise ValidationError("Indica el monto del descuento.", details={"value_cents": "Obligatorio."})
    if out["kind"] == "percent" and not out["percent"]:
        raise ValidationError("Indica el porcentaje.", details={"percent": "Obligatorio."})
    if out["kind"] == "free_product" and not out["product_id"]:
        raise ValidationError("Selecciona el producto.", details={"product_id": "Obligatorio."})
    return _save("coupons", COUPON_COLS, _dates(out), coupon_id)


def list_coupons(page, size, source="admin"):
    db = get_db()
    total = db.scalar("SELECT COUNT(*) AS n FROM coupons WHERE source = ?", (source,))
    rows = db.all("SELECT * FROM coupons WHERE source = ? ORDER BY created_at DESC LIMIT ? OFFSET ?", (source, size, (page - 1) * size))
    for r in rows:
        r["is_active"] = bool(r["is_active"])
    return rows, total


# ---------------------------------------------------------------- promociones
PROMO_COLS = ("name", "description", "kind", "value", "target", "target_id", "starts_at", "ends_at", "is_active")


def save_promotion(data: dict, promo_id: int | None) -> dict:
    out = (V(data).str("name", max_len=120).str("description", required=False, max_len=300)
           .choice("kind", {"percent", "fixed"}).int("value", min_value=1)
           .choice("target", {"all", "category", "product"}, required=False, default="all").int("target_id", required=False)
           .str("starts_at", required=False).str("ends_at", required=False).bool("is_active", default=True)).check()
    if out["kind"] == "percent" and out["value"] > 90:
        raise ValidationError("El porcentaje máximo es 90.", details={"value": "Máximo 90."})
    if out["target"] != "all" and not out["target_id"]:
        raise ValidationError("Selecciona a qué se aplica la promoción.", details={"target_id": "Obligatorio."})
    result = _save("promotions", PROMO_COLS, _dates(out), promo_id)
    promotion_service.invalidate()
    return result


def list_promotions():
    rows = get_db().all("SELECT * FROM promotions ORDER BY created_at DESC LIMIT 200")
    for r in rows:
        r["is_active"] = bool(r["is_active"])
    return rows


def delete(table: str, entity_id: int) -> None:
    if table not in {"coupons", "promotions", "rewards"}:
        raise ValidationError("Tabla no permitida.")
    db = get_db()
    if table == "rewards" and db.one("SELECT id FROM reward_redemptions WHERE reward_id = ? LIMIT 1", (entity_id,)):
        db.execute("UPDATE rewards SET is_active = FALSE, updated_at = ? WHERE id = ?", (now_iso(), entity_id))
        return
    if table == "coupons" and db.one("SELECT id FROM coupon_usages WHERE coupon_id = ? LIMIT 1", (entity_id,)):
        db.execute("UPDATE coupons SET is_active = FALSE, updated_at = ? WHERE id = ?", (now_iso(), entity_id))
        return
    if not db.execute(f"DELETE FROM {table} WHERE id = ?", (entity_id,)):
        raise NotFound("Registro no encontrado.")
    promotion_service.invalidate()


# ---------------------------------------------------------------- recompensas
REWARD_COLS = ("name", "description", "kind", "points_cost", "value_cents", "percent", "product_id", "stock",
               "per_user_limit", "coupon_valid_days", "is_active", "starts_at", "ends_at")


def save_reward(data: dict, reward_id: int | None) -> dict:
    out = (V(data).str("name", max_len=120).str("description", required=False, max_len=300)
           .choice("kind", reward_service.KINDS).int("points_cost", min_value=1)
           .int("value_cents", required=False, min_value=0, default=0)
           .int("percent", required=False, min_value=0, max_value=100, default=0).int("product_id", required=False)
           .int("stock", required=False, min_value=0).int("per_user_limit", required=False, min_value=1)
           .int("coupon_valid_days", required=False, min_value=1, max_value=365, default=30)
           .bool("is_active", default=True).str("starts_at", required=False).str("ends_at", required=False)).check()
    if out["kind"] == "fixed_discount" and not out["value_cents"]:
        raise ValidationError("Indica el valor del descuento.", details={"value_cents": "Obligatorio."})
    if out["kind"] == "percent_discount" and not out["percent"]:
        raise ValidationError("Indica el porcentaje.", details={"percent": "Obligatorio."})
    if out["kind"] == "free_product" and not out["product_id"]:
        raise ValidationError("Selecciona el producto.", details={"product_id": "Obligatorio."})
    return _save("rewards", REWARD_COLS, _dates(out), reward_id)


def list_rewards():
    rows = get_db().all(
        """SELECT r.*, (SELECT COUNT(*) FROM reward_redemptions rr WHERE rr.reward_id = r.id) AS redemptions
           FROM rewards r ORDER BY r.points_cost""")
    for r in rows:
        r["is_active"] = bool(r["is_active"])
    return rows
