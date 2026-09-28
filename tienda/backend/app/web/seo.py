"""Rutas web: shell del frontend con metadatos SEO por página, sitemap y robots.

El frontend es una SPA, pero los buscadores y las redes sociales reciben el
título, la descripción, Open Graph y datos estructurados (JSON-LD) correctos
porque el servidor los inserta en el HTML antes de enviarlo.
"""
from __future__ import annotations

import html
import json
from functools import lru_cache
from xml.sax.saxutils import escape as xml_escape

from flask import Blueprint, Response, abort, current_app, request, send_from_directory

from app.core.errors import NotFound
from app.db import get_db
from app.services import catalog_service, settings_service

web = Blueprint("web", __name__)

STATIC_DIRS = ("assets", "src", "styles")
import re

KNOWN_ROUTES = re.compile(
    r"^/(|catalogo|ofertas|buscar|carrito|checkout|puntos|recompensas|contacto|terminos|privacidad|favoritos|"
    r"iniciar-sesion|registro|recuperar-contrasena|restablecer-contrasena|cuenta(/.*)?|pedido/[^/]+|"
    r"producto/[^/]+|categoria/[^/]+)/?$"
)
NOINDEX_PREFIXES = ("/cuenta", "/carrito", "/checkout", "/iniciar-sesion", "/registro", "/recuperar", "/restablecer", "/admin", "/pedido")


@lru_cache(maxsize=4)
def _read(path: str, mtime: float) -> str:
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _template(name: str) -> str:
    path = current_app.config["FRONTEND_DIR"] / name
    if not path.exists():
        return "<!doctype html><html lang='es'><head><!--SEO--></head><body><div id='app'></div></body></html>"
    return _read(str(path), path.stat().st_mtime)


def _meta_tags(title: str, description: str, *, image: str | None = None, og_type: str = "website",
               noindex: bool = False, json_ld: dict | None = None, canonical: str | None = None) -> str:
    base = current_app.config["PUBLIC_BASE_URL"]
    e = lambda v: html.escape(v or "", quote=True)
    canonical = canonical or f"{base}{request.path}"
    tags = [
        f"<title>{e(title)}</title>",
        f'<meta name="description" content="{e(description)}">',
        f'<link rel="canonical" href="{e(canonical)}">',
        f'<meta property="og:title" content="{e(title)}">',
        f'<meta property="og:description" content="{e(description)}">',
        f'<meta property="og:type" content="{og_type}">',
        f'<meta property="og:url" content="{e(canonical)}">',
        '<meta name="twitter:card" content="summary_large_image">',
    ]
    if image:
        img = image if image.startswith("http") else f"{base}{image}"
        tags.append(f'<meta property="og:image" content="{e(img)}">')
    if noindex:
        tags.append('<meta name="robots" content="noindex, nofollow">')
    if json_ld:
        payload = json.dumps(json_ld, ensure_ascii=False).replace("</", "<\\/")
        tags.append(f'<script type="application/ld+json">{payload}</script>')
    return "\n    ".join(tags)


def _page_meta(path: str) -> str:
    s = settings_service.all_settings()
    store, seo = s["store"], s["seo"]
    name = store.get("name") or "Tienda"
    default_title = seo.get("default_title") or name
    desc = seo.get("default_description") or ""
    base = current_app.config["PUBLIC_BASE_URL"]
    if path.startswith("/producto/"):
        slug = path.split("/", 2)[2].strip("/")
        try:
            p = catalog_service.get_product(slug)
        except NotFound:
            raise
        image = p["images"][0]["url"] if p["images"] else None
        json_ld = {
            "@context": "https://schema.org", "@type": "Product", "name": p["name"], "sku": p["sku"],
            "description": p["seo_description"] or p.get("short_description") or "",
            "image": [i["url"] if i["url"].startswith("http") else base + i["url"] for i in p["images"]],
            "offers": {
                "@type": "Offer", "priceCurrency": store.get("currency", "GTQ"),
                "price": f"{p['price_cents'] / 100:.2f}", "url": f"{base}/producto/{p['slug']}",
                "availability": "https://schema.org/InStock" if p["stock"] > 0 else "https://schema.org/OutOfStock",
            },
        }
        if p["category"]:
            json_ld["category"] = p["category"]["name"]
        return _meta_tags(f"{p['seo_title']} | {name}", p["seo_description"] or desc, image=image,
                          og_type="product", json_ld=json_ld, noindex=p["is_demo"])
    if path.startswith("/categoria/"):
        slug = path.split("/", 2)[2].strip("/")
        try:
            c = catalog_service.category_by_slug(slug)
        except NotFound:
            raise
        return _meta_tags(f"{c['seo_title'] or c['name']} | {name}", c["seo_description"] or c["description"] or desc,
                          image=c.get("image_url"))
    titles = {"/": default_title, "/catalogo": f"Catálogo | {name}", "/contacto": f"Contacto | {name}",
              "/puntos": f"{s['loyalty'].get('program_name') or 'Programa de puntos'} | {name}",
              "/ofertas": f"Ofertas | {name}"}
    title = titles.get(path.rstrip("/") or "/", name)
    json_ld = {"@context": "https://schema.org", "@type": "Store", "name": name, "url": base} if path == "/" else None
    return _meta_tags(title, desc, image=seo.get("og_image"), noindex=path.startswith(NOINDEX_PREFIXES), json_ld=json_ld)


def render_shell(status: int = 200, admin: bool = False):
    if admin:
        body = _template("admin/index.html").replace(
            "<!--SEO-->", '<title>Panel de administración</title>\n    <meta name="robots" content="noindex, nofollow">')
        return Response(body, status=status, mimetype="text/html")
    if status == 200 and not KNOWN_ROUTES.match(request.path):
        status = 404
    try:
        meta = _page_meta(request.path) if status == 200 else _meta_tags(
            "Página no encontrada" if status == 404 else "Error del servidor", "", noindex=True)
    except NotFound:
        status = 404
        meta = _meta_tags("Página no encontrada", "", noindex=True)
    except Exception:  # la metadata nunca debe tumbar la página
        current_app.logger.exception("Error generando metadatos SEO")
        meta = _meta_tags("Tienda", "", noindex=True)
    body = _template("index.html").replace("<!--SEO-->", meta)
    resp = Response(body, status=status, mimetype="text/html")
    resp.headers["Cache-Control"] = "no-cache"
    return resp


@web.get("/robots.txt")
def robots():
    base = current_app.config["PUBLIC_BASE_URL"]
    lines = ["User-agent: *"]
    lines += [f"Disallow: {p}" for p in NOINDEX_PREFIXES] + ["Disallow: /api/", f"Sitemap: {base}/sitemap.xml"]
    return Response("\n".join(lines) + "\n", mimetype="text/plain")


@web.get("/sitemap.xml")
def sitemap():
    base = current_app.config["PUBLIC_BASE_URL"]
    db = get_db()
    urls = [(f"{base}/", None), (f"{base}/catalogo", None), (f"{base}/puntos", None), (f"{base}/contacto", None)]
    urls += [(f"{base}/categoria/{c['slug']}", None) for c in catalog_service.all_categories()]
    # Para catálogos muy grandes (>50.000 URLs) dividir en un índice de sitemaps.
    for p in db.all("SELECT slug, updated_at FROM products WHERE status = 'active' AND is_demo = FALSE ORDER BY id LIMIT 50000"):
        urls.append((f"{base}/producto/{p['slug']}", str(p["updated_at"])[:10]))
    body = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for loc, lastmod in urls:
        body.append(f"  <url><loc>{xml_escape(loc)}</loc>" + (f"<lastmod>{lastmod}</lastmod>" if lastmod else "") + "</url>")
    body.append("</urlset>")
    return Response("\n".join(body), mimetype="application/xml")


@web.get("/uploads/<path:filename>")
def uploads(filename):
    resp = send_from_directory(current_app.config["UPLOAD_DIR"], filename, max_age=31536000)
    return resp


@web.get("/<any(assets, src, styles):folder>/<path:filename>")
def static_files(folder, filename):
    if not current_app.config["SERVE_FRONTEND"]:
        abort(404)
    # En desarrollo sin caché larga; en producción nginx sirve estos archivos.
    return send_from_directory(current_app.config["FRONTEND_DIR"] / folder, filename, max_age=0)


@web.get("/admin")
@web.get("/admin/<path:_rest>")
def admin_shell(_rest=None):
    return render_shell(admin=True)


@web.get("/")
@web.get("/<path:_path>")
def spa(_path=None):
    if request.path.startswith("/api/"):
        abort(404)
    return render_shell()
