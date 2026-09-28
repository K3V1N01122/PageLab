from flask import current_app, jsonify, request

from app.api.v1 import api_v1
from app.core.pagination import page_params, page_result
from app.services import catalog_service


def _public_cache(resp):
    resp.headers["Cache-Control"] = f"public, max-age={current_app.config['CACHE_PUBLIC_SECONDS']}"
    return resp


@api_v1.get("/categories")
def categories():
    return _public_cache(jsonify({"items": catalog_service.category_tree()}))


@api_v1.get("/categories/<slug>")
def category(slug):
    cat = catalog_service.category_by_slug(slug)
    cat["breadcrumb"] = catalog_service.breadcrumb(cat["id"])
    return _public_cache(jsonify(cat))


@api_v1.get("/products")
def products():
    page, size = page_params()
    params = {k: request.args.get(k) for k in ("q", "category", "tag", "min_price", "max_price", "in_stock", "sort", "featured", "on_sale")}
    items, total = catalog_service.list_products(params, page, size)
    return _public_cache(jsonify(page_result(items, total, page, size)))


@api_v1.get("/products/<slug>")
def product(slug):
    return _public_cache(jsonify(catalog_service.get_product(slug)))


@api_v1.get("/search/suggest")
def suggest():
    return _public_cache(jsonify({"items": catalog_service.suggest(request.args.get("q", ""))}))
