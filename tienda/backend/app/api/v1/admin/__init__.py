"""Endpoints del panel (/api/v1/admin/...). Cada ruta exige permisos
concretos; el rol de cliente no tiene ninguno."""


def register(bp):
    from app.api.v1.admin import catalog, loyalty, orders, promotions, settings, stats, users
    for module in (catalog, orders, users, loyalty, promotions, stats, settings):
        module.routes(bp)
