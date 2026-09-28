# Seguridad

| Amenaza | Medida | Dónde | Prueba |
|---|---|---|---|
| Contraseñas filtradas | scrypt con sal; nunca en texto plano | `core/security.py` | `test_register_creates_user_hashed_password…` |
| Enumeración de cuentas | Mismo mensaje y tiempo similar (hash ficticio) si el correo no existe; recuperación responde siempre igual | `user_service.authenticate` | `test_unknown_email_same_error…`, `test_forgot_password_does_not_reveal…` |
| Fuerza bruta | Bloqueo de 15 min tras 5 fallos; límite por IP (10/min) y por cuenta (20/15 min) | `user_service`, `core/ratelimit.py` | `test_wrong_password_generic_message_and_lockout`, `test_rate_limit` |
| Robo de sesión | Token aleatorio de 256 bits, guardado como hash; cookie `HttpOnly`, `SameSite=Lax`, `Secure` en producción; revocación al cambiar contraseña/rol o desactivar | `core/auth.py` | `test_session_token_stored_hashed`, `test_change_password_revokes…` |
| CSRF | Doble envío (cookie + cabecera) y verificación de `Origin` | `core/csrf.py` | `test_csrf_required…`, `test_foreign_origin_rejected` |
| XSS | Frontend: plantillas con escape automático, sin `innerHTML` con datos crudos; CSP estricta sin scripts en línea; metadatos escapados en el servidor; enlaces de configuración limitados a `https://` | `utils/html.js`, `core/headers.py`, `settings_service` | `test_meta_is_escaped`, `test_settings_reject_dangerous_links` |
| Inyección SQL | 100 % consultas parametrizadas; los únicos fragmentos dinámicos (orden, columnas) salen de listas cerradas en el código | `db/`, `services/` | `test_sql_injection_in_search_is_inert` |
| Manipulación de precios, totales, descuentos | El servidor recalcula todo con `pricing_service.quote`; ignora campos de precio enviados; `expected_total_cents` detecta cambios | `pricing_service`, `order_service` | `test_client_cannot_send_prices`, `test_manipulated_total_is_ignored` |
| Manipulación de puntos | Solo el backend modifica saldos; UPDATE condicional impide negativos; movimiento en la misma transacción | `loyalty_service` | `test_points_cannot_be_set_from_frontend`, `test_points_cannot_be_double_spent` |
| Escalación de privilegios | Permisos validados en cada endpoint; el registro ignora `role`; nadie puede cambiar su propio rol | `core/auth.permission_required`, `admin_service` | `test_role_cannot_be_self_assigned`, `test_limited_role_only_gets…` |
| Acceso a datos ajenos | Toda consulta de cuenta filtra por `user_id` de la sesión | `order_service`, `user_service` | `test_user_cannot_see_other_users_orders` |
| Operaciones duplicadas | Claves de idempotencia únicas en pedidos y canjes | `order_service`, `reward_service` | `test_idempotent_checkout`, `test_duplicate_checkout_requests…` |
| Sobreventa | `UPDATE products SET stock = stock - n WHERE stock >= n` | `order_service.place_order` | `test_no_overselling_under_concurrent_checkouts` |
| Archivos maliciosos | Se verifica que sea imagen real con Pillow y se re-codifica a WebP con nombre aleatorio | `storage_service` | `test_image_upload_validates_content` |
| Redirección abierta | `next` solo acepta rutas internas | `pages/login.js` | — |
| Fuga de errores | Respuestas 500 genéricas con referencia; detalle solo en el log | `core/errors.py` | `test_errors_do_not_leak_internals` |
| Clickjacking y otros | `X-Frame-Options: DENY`, `nosniff`, `Referrer-Policy`, `Permissions-Policy`, HSTS con HTTPS | `core/headers.py` | `test_security_headers` |
| Secretos | Variables de entorno; producción no arranca sin `SECRET_KEY` fuerte ni con el pago de prueba | `config.py` | — |
| Trazabilidad | Registro de auditoría de acciones administrativas y cambios de seguridad | `core/audit.py` | — |

## Recomendaciones operativas

- HTTPS obligatorio en producción (cookies `Secure` y HSTS dependen de ello).
- `TRUST_PROXY_HEADERS=true` solo detrás de un proxy que **sobrescriba** `X-Forwarded-For`
  (la configuración de nginx incluida lo hace).
- Rotar `SECRET_KEY` invalida solo datos firmados; las sesiones viven en la base.
- Revisar `audit_log` periódicamente y respaldar la base a diario.
- Agregar verificación de correo y 2FA para cuentas de personal cuando se defina el proveedor
  de correo.
