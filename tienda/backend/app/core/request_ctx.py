from flask import current_app, request


def client_ip() -> str:
    if current_app.config.get("TRUST_PROXY_HEADERS"):
        fwd = request.headers.get("X-Forwarded-For", "")
        if fwd:
            return fwd.split(",")[0].strip()[:64]
    return (request.remote_addr or "unknown")[:64]


def json_body() -> dict:
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else {}
