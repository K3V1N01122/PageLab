from flask import g, jsonify, request

from app.api.v1 import api_v1
from app.core import auth, ratelimit
from app.core.audit import audit
from app.core.errors import ValidationError
from app.core.request_ctx import json_body
from app.core.validation import V
from app.services import user_service


@api_v1.get("/auth/me")
def me():
    return jsonify({"user": user_service.public_user(g.user) if g.user else None})


@api_v1.post("/auth/register")
@ratelimit.limit("auth", "RATE_LIMIT_AUTH")
def register():
    body = json_body()
    data = (V(body).str("first_name", max_len=80).str("last_name", max_len=80).email()
            .phone().password().str("password_confirm", strip=False, max_len=128).bool("accept_terms")).check()
    if data["password"] != data["password_confirm"]:
        raise ValidationError("Revisa los campos marcados.", details={"password_confirm": "Las contraseñas no coinciden."})
    if not data["accept_terms"]:
        raise ValidationError("Revisa los campos marcados.", details={"accept_terms": "Debes aceptar los términos y condiciones."})
    user = user_service.register(data)
    token, max_age = auth.create_session(user["id"], remember=False)
    resp = jsonify({"user": user_service.public_user(user_service.with_role(user["id"]))})
    auth.set_session_cookie(resp, token, max_age)
    return resp, 201


@api_v1.post("/auth/login")
@ratelimit.limit("auth", "RATE_LIMIT_AUTH")
def login():
    body = json_body()
    data = V(body).email().str("password", strip=False, max_len=128).bool("remember").check()
    # Límite adicional por cuenta, independiente de la IP (fuerza bruta distribuida).
    ratelimit.check("login-account", "20/900", key=data["email"])
    user = user_service.authenticate(data["email"], data["password"])
    token, max_age = auth.create_session(user["id"], remember=data["remember"])
    # Las apps móviles (X-Client: mobile) reciben el token para usarlo como Bearer.
    mobile = request.headers.get("X-Client") == "mobile"
    resp = jsonify({"user": user_service.public_user(user_service.with_role(user["id"])), "token": token if mobile else None})
    auth.set_session_cookie(resp, token, max_age)
    return resp


@api_v1.post("/auth/logout")
def logout():
    if g.get("session"):
        auth.revoke_session(g.session["id"])
    resp = jsonify({"ok": True})
    auth.clear_session_cookie(resp)
    return resp


@api_v1.post("/auth/password/forgot")
@ratelimit.limit("auth", "RATE_LIMIT_AUTH")
def forgot_password():
    data = V(json_body()).email().check()
    ratelimit.check("forgot-account", "3/900", key=data["email"])
    user_service.request_password_reset(data["email"])
    return jsonify({"message": "Si el correo está registrado, recibirás un enlace para restablecer tu contraseña."})


@api_v1.post("/auth/password/reset")
@ratelimit.limit("auth", "RATE_LIMIT_AUTH")
def reset_password():
    body = json_body()
    data = V(body).str("token", max_len=200).password().str("password_confirm", strip=False, max_len=128).check()
    if data["password"] != data["password_confirm"]:
        raise ValidationError("Revisa los campos marcados.", details={"password_confirm": "Las contraseñas no coinciden."})
    user_service.reset_password(data["token"], data["password"])
    return jsonify({"message": "Tu contraseña se actualizó. Ya puedes iniciar sesión."})


@api_v1.post("/auth/password/change")
@auth.login_required
@ratelimit.limit("auth", "RATE_LIMIT_AUTH")
def change_password():
    body = json_body()
    data = V(body).str("current_password", strip=False, max_len=128).password().str("password_confirm", strip=False, max_len=128).check()
    if data["password"] != data["password_confirm"]:
        raise ValidationError("Revisa los campos marcados.", details={"password_confirm": "Las contraseñas no coinciden."})
    user_service.change_password(g.user["id"], data["current_password"], data["password"], g.session["id"])
    audit("password_changed", "user", g.user["id"])
    return jsonify({"message": "Contraseña actualizada. Cerramos tus otras sesiones."})
