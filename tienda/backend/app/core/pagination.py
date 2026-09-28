from flask import request

MAX_PAGE_SIZE = 60


def page_params(default_size: int = 24) -> tuple[int, int]:
    try:
        page = max(1, int(request.args.get("page", 1)))
    except ValueError:
        page = 1
    try:
        size = int(request.args.get("page_size", default_size))
    except ValueError:
        size = default_size
    size = max(1, min(size, MAX_PAGE_SIZE))
    return page, size


def page_result(items, total, page, size):
    return {
        "items": items,
        "pagination": {
            "page": page, "page_size": size, "total": total,
            "pages": max(1, -(-total // size)),
        },
    }
