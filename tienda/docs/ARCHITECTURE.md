# Arquitectura

## Vista general

```
Navegador ──► nginx ──► estáticos (src/, styles/, assets/, uploads/)
                  └──► gunicorn ─► Flask
                                    ├─ /api/v1/*        API REST (JSON)
                                    ├─ /admin, /admin/* shell del panel
                                    └─ /*               shell de la tienda + metadatos SEO
                                           │
                                           ▼
                                      PostgreSQL
```

- **Frontend y backend separados**: el frontend solo habla con el backend a través de la API
  versionada `/api/v1`. Una app móvil o una integración externa pueden usar la misma API
  (autenticación con `Authorization: Bearer`).
- **Tienda y panel son aplicaciones distintas** que comparten utilidades (`src/utils`,
  `src/services/api.js`, estilos base). El panel se carga solo para personal autorizado.

## Capas del backend

| Capa | Carpeta | Responsabilidad |
|---|---|---|
| HTTP | `api/v1/` | Leer y validar la petición, llamar al servicio, responder JSON. Sin lógica de negocio. |
| Dominio | `services/` | Reglas de negocio, transacciones y consultas. |
| Pagos | `payments/` | Interfaz `PaymentProvider` y proveedores intercambiables. |
| Núcleo | `core/` | Autenticación, permisos, CSRF, rate limiting, validación, errores, auditoría. |
| Datos | `db/` | Conexión portable SQLite/PostgreSQL, migraciones, datos demo. |
| Web | `web/seo.py` | Shell HTML con metadatos por página, sitemap, robots, 404 reales. |

`services/pricing_service.quote()` es la **única** función que calcula montos. El carrito, la
vista previa del checkout y la creación del pedido la usan con datos de la base; el cliente
solo envía IDs, cantidades, un código de cupón y cuántos puntos quiere usar.

## Flujo de una compra

1. El navegador envía `POST /api/v1/checkout` con una `idempotency_key` generada al abrir el
   checkout y el total que el cliente vio (`expected_total_cents`).
2. Si ya existe un pedido con esa clave para el usuario, se devuelve el mismo (doble clic o
   reintento de red).
3. En **una transacción**:
   - Se recalcula el total con `quote()`. Si cambió respecto a lo que vio el cliente → `409
     price_changed` con el nuevo resumen; nada se guarda.
   - Se crea el pedido y sus líneas (con copia del nombre, SKU y precio).
   - Se descuenta el stock con `UPDATE ... WHERE stock >= cantidad`. Si otra compra se llevó
     las últimas unidades, falla y se revierte todo.
   - Se consume el cupón con `UPDATE ... WHERE uses_count < max_uses`.
   - Se descuentan los puntos con `UPDATE ... WHERE points_balance >= n` y se registra el
     movimiento; los puntos ganados quedan **pendientes**.
   - Se crea el pago con el proveedor elegido y se vacía el carrito.
4. Tras confirmar la transacción se envía el correo de confirmación.
5. Al llegar al estado configurado (por defecto *Entregado*) los puntos pendientes pasan a
   disponibles. Si el pedido se cancela: se repone el stock, se devuelven los puntos usados,
   se anulan los ganados y se libera el cupón.

## Estados de pedido

`pending → paid → preparing → shipped → delivered`, con `cancelled` posible hasta antes del
envío. Las etiquetas viven en la tabla `order_statuses` y las transiciones permitidas en
`order_service.TRANSITIONS`. Para un estado nuevo: migración que lo inserte + agregarlo a
`TRANSITIONS`. Cada cambio queda en `order_status_history` con quién y cuándo, y usa bloqueo
optimista (`WHERE status = estado_actual`) para que dos administradores no se pisen.

## Modelo de datos

```
roles ─< role_permissions >─ permissions
roles ─< users ─┬─ loyalty_cards (1:1)
                ├─< sessions, password_resets, addresses, favorites
                ├─ carts ─< cart_items >─ products
                ├─< orders ─┬─< order_items >─ products
                │           ├─< order_status_history
                │           ├─< payments
                │           └─< coupon_usages >─ coupons
                ├─< point_movements (earn/spend/redeem/refund/revoke/adjust; pending/posted/cancelled)
                └─< reward_redemptions >─ rewards   (genera un coupon personal)
categories (árbol por parent_id) ─< products ─┬─< product_images
                                               ├─< product_tags >─ tags
                                               ├─< product_related
                                               └─< inventory_movements
promotions (all | category | product)   settings (clave → JSON)   rate_limits   audit_log
```

Decisiones del modelo:
- Dinero en **centavos enteros**; nunca `float`.
- `order_items` guarda copia de nombre, SKU y precio: el historial no cambia si luego se edita
  el producto. Por eso un producto con ventas se **archiva** en vez de borrarse.
- El saldo de puntos está en `loyalty_cards` (lectura rápida) y cada cambio tiene su fila en
  `point_movements` dentro de la misma transacción, de modo que el historial siempre cuadra.
- `search_text` es texto normalizado (minúsculas, sin tildes) para búsquedas sin depender del
  motor. Con catálogos grandes, reemplazar por búsqueda de texto completo de PostgreSQL
  (`tsvector` + índice GIN) sin cambiar la API.
- Índices en todas las claves foráneas consultadas y en los órdenes de listado usados
  (`status + created_at`, `category_id + status`, `price`, `sold_count`, etc.).

## Escalabilidad

| Tema | Implementado | Siguiente paso cuando crezca |
|---|---|---|
| Concurrencia | UPDATE condicionales, transacciones, claves de idempotencia, bloqueo optimista | — |
| Paginación | Toda lista pública y del panel (máx. 60 por página) | Paginación por cursor en listados muy grandes |
| Caché | Configuración, categorías y promociones en memoria (30–60 s); `Cache-Control` público en catálogo | Redis compartido; CDN delante de nginx |
| Imágenes | WebP optimizado en 2 tamaños, `loading="lazy"`, caché de 1 año | Almacenamiento S3 + CDN |
| Compresión | gzip en nginx | Brotli |
| Rate limiting | Contadores en la base (compartidos entre instancias) | Backend Redis (reimplementar `ratelimit._hit`) |
| Horizontal | App sin estado: se pueden correr N instancias detrás de nginx | Balanceador + PgBouncer |
| Trabajos lentos | Correo síncrono con manejo de fallos (no rompe la compra) | Cola (RQ/Celery) para correos, webhooks, reportes |
| Estadísticas | Consultas agregadas sobre pedidos | Tabla de agregados diarios |
| Carga inicial | Páginas cargadas bajo demanda (import dinámico) | — |

## Preparado para crecer

- **App móvil / API pública**: API versionada, errores con códigos estables, login con
  `X-Client: mobile` devuelve un token Bearer.
- **Pagos**: nuevo archivo en `payments/providers/` + registro + variable de entorno.
- **Notificaciones** (correo, WhatsApp, push): canales en `notification_service.py`.
- **Niveles VIP**: `loyalty_cards.tier` ya existe; falta la regla de cálculo.
- **Nuevas recompensas**: agregar un handler en `reward_service.HANDLERS`.
- **Roles**: `ROLES`/`PERMISSIONS` en `db/migrate.py`, sin tocar endpoints.
- **Marketplace / múltiples vendedores**: agregar `vendor_id` a productos y pedidos es una
  migración aditiva; los servicios ya centralizan las consultas.
