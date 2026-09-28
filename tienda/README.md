# Tienda en línea: base de e-commerce lista para crecer

Plataforma de comercio electrónico completa: catálogo dinámico, carrito, checkout,
pedidos, cuentas de cliente, tarjeta virtual de fidelidad con puntos y recompensas,
y un panel de administración con roles y permisos.

Los productos, el logo, los colores, los datos de contacto, el proveedor de pagos y la
empresa de envíos **aún no están definidos**. Todo eso es configurable desde el panel o
mediante variables de entorno, y los datos incluidos son de **demostración** y están
claramente marcados (ver [Datos de demostración](#datos-de-demostración)).

---

## Contenido

1. [Tecnologías](#tecnologías)
2. [Estructura de carpetas](#estructura-de-carpetas)
3. [Instalación rápida (desarrollo)](#instalación-rápida-desarrollo)
4. [Variables de entorno](#variables-de-entorno)
5. [Base de datos y migraciones](#base-de-datos-y-migraciones)
6. [Ejecutar backend y frontend](#ejecutar-backend-y-frontend)
7. [Crear un administrador](#crear-un-administrador)
8. [Pruebas](#pruebas)
9. [Datos de demostración](#datos-de-demostración)
10. [Deployment (producción)](#deployment-producción)
11. [Qué está pendiente de definir](#qué-está-pendiente-de-definir)
12. [Documentación técnica](#documentación-técnica)

---

## Tecnologías

| Capa | Tecnología | Por qué |
|---|---|---|
| Backend / API | Python 3.12, Flask 3.1 | Estable, conocido, pocas dependencias |
| Base de datos | PostgreSQL 16 (producción), SQLite (desarrollo y pruebas) | Relacional, transacciones, índices |
| Acceso a datos | SQL parametrizado con una capa propia (`app/db`) | Control total en operaciones de dinero, stock y puntos |
| Contraseñas | scrypt (Werkzeug) | Hash lento con sal, estándar actual |
| Imágenes | Pillow | Validación real del archivo y conversión a WebP optimizado |
| Servidor | gunicorn + nginx | Producción: procesos múltiples, compresión, estáticos |
| Frontend | HTML, CSS y JavaScript moderno (módulos ES), sin paso de compilación | Sin dependencias ni herramientas de build que mantener |
| Pruebas | `unittest` (biblioteca estándar) + Playwright opcional para E2E | Se ejecutan en cualquier máquina con Python |

Dependencias de ejecución: solo 4 (`backend/requirements.txt`). El frontend no tiene
dependencias. Las decisiones están explicadas en [docs/DECISIONS.md](docs/DECISIONS.md).

---

## Estructura de carpetas

```
tienda/
├── backend/
│   ├── app/
│   │   ├── __init__.py          Fábrica de la app (middlewares, blueprints)
│   │   ├── config.py            Configuración por entorno (development/testing/production)
│   │   ├── core/                Seguridad, autenticación, CSRF, rate limiting, validación, errores
│   │   ├── db/                  Conexión, migraciones SQL versionadas y datos de demostración
│   │   ├── services/            Lógica de negocio (precios, carrito, pedidos, puntos, recompensas…)
│   │   ├── payments/            Interfaz de proveedores de pago + implementaciones
│   │   ├── api/v1/              Endpoints REST públicos, de cliente y de administración (admin/)
│   │   └── web/seo.py           Páginas HTML con metadatos SEO, sitemap y robots.txt
│   ├── tests/                   Pruebas automáticas (69)
│   ├── manage.py                CLI: migrate, seed-demo, create-admin, run
│   ├── wsgi.py                  Punto de entrada para gunicorn
│   └── requirements*.txt
├── frontend/
│   ├── index.html               Shell de la tienda
│   ├── admin/index.html         Shell del panel de administración (aplicación separada)
│   ├── src/
│   │   ├── main.js, router.js   Arranque y rutas con URLs limpias
│   │   ├── services/            Cliente de la API, sesión, carrito
│   │   ├── store/               Estado global mínimo
│   │   ├── components/          Encabezado, pie, tarjeta de producto, tarjeta de fidelidad…
│   │   ├── pages/               Páginas de la tienda y de la cuenta del cliente
│   │   ├── admin/               Panel de administración (páginas y utilidades propias)
│   │   └── utils/               Plantillas seguras (anti-XSS), formato, formularios
│   ├── styles/                  tokens, base, layout, componentes, páginas, panel
│   └── assets/
├── e2e/                         Pruebas de navegador (Playwright, opcionales)
├── deploy/nginx.conf
├── docs/                        Arquitectura, decisiones, API y seguridad
├── Dockerfile, docker-compose.yml, .env.example
└── README.md
```

---

## Instalación rápida (desarrollo)

Requisitos: **Python 3.11 o superior**. No se necesita Node.js.

```bash
cd tienda
python3 -m venv .venv
source .venv/bin/activate            # En Windows: .venv\Scripts\activate
pip install -r backend/requirements-dev.txt

cp .env.example .env                  # opcional en desarrollo
cd backend
python manage.py migrate              # crea la base SQLite en backend/instance/
python manage.py seed-demo            # carga productos y usuarios de DEMOSTRACIÓN
python manage.py run                  # http://127.0.0.1:5000
```

- Tienda: <http://127.0.0.1:5000>
- Panel: <http://127.0.0.1:5000/admin>

> En desarrollo, `psycopg` y `gunicorn` se instalan pero no se usan. Si prefieres no
> instalarlos: `pip install "Flask>=3.1,<3.2" "Pillow>=11,<13"`.

`manage.py` carga automáticamente el archivo `tienda/.env` si existe (las variables del
sistema tienen prioridad y las vacías se ignoran). En Windows, después de la primera
instalación basta con hacer **doble clic en `iniciar.bat`**: aplica migraciones pendientes,
abre el navegador y enciende el servidor.

---

## Variables de entorno

Todas están documentadas en [`.env.example`](.env.example). Las más importantes:

| Variable | Desarrollo | Producción |
|---|---|---|
| `APP_ENV` | `development` | `production` |
| `SECRET_KEY` | automática (insegura) | **obligatoria**, 32+ caracteres |
| `DATABASE_URL` | SQLite por defecto | **PostgreSQL obligatorio** |
| `PUBLIC_BASE_URL` | `http://localhost:5000` | `https://tudominio.com` |
| `SESSION_COOKIE_SECURE` | `false` | `true` (por defecto) |
| `PAYMENT_PROVIDERS` | incluye `sandbox_card` | `cash_on_delivery,bank_transfer` |
| `SERVE_FRONTEND` | `true` | `false` (lo sirve nginx) |
| `TRUST_PROXY_HEADERS` | `false` | `true` detrás de nginx |

En producción la aplicación **no arranca** si falta `SECRET_KEY`, si la base es SQLite o si
se habilitó el proveedor de pago de prueba (`ProductionConfig.validate`).

Los valores de negocio (nombre de la tienda, colores, contacto, redes, puntos, envíos, SEO)
**no** son variables de entorno: se editan en *Panel > Configuración* y *Panel > Fidelización*
y se guardan en la tabla `settings`.

---

## Base de datos y migraciones

- Las migraciones están en `backend/app/db/migrations/NNNN_nombre.sql`, se aplican en orden y
  quedan registradas en `schema_migrations`. El mismo SQL sirve para SQLite y PostgreSQL
  (tokens `{{ID}}`, `{{TS}}`, `{{JSON}}`, `{{BOOL}}` que el migrador traduce).
- `python manage.py migrate` aplica las migraciones pendientes y crea los datos de referencia
  obligatorios (roles, permisos, estados de pedido y configuración inicial). Es idempotente.
- Para un cambio de esquema: crea `0002_descripcion.sql` con los `ALTER TABLE` necesarios y
  ejecuta `migrate`. No modifiques migraciones ya aplicadas.

PostgreSQL local rápido:

```bash
docker run -d --name tienda-pg -e POSTGRES_PASSWORD=clave -e POSTGRES_DB=tienda -p 5432:5432 postgres:16-alpine
export DATABASE_URL=postgresql://postgres:clave@localhost:5432/tienda
python manage.py migrate
```

El modelo de datos está descrito en [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md#modelo-de-datos).

---

## Ejecutar backend y frontend

**Desarrollo:** un solo proceso. `python manage.py run` levanta la API en `/api/v1`, sirve el
frontend (`frontend/`) y las imágenes subidas. El frontend no requiere compilación: edita un
archivo y recarga el navegador.

**Frontend separado (opcional):** el frontend puede alojarse en otro dominio o CDN. En ese caso
agrega ese origen a `CORS_ALLOWED_ORIGINS` y sirve el HTML a través del backend para conservar
los metadatos SEO (ver [docs/DECISIONS.md](docs/DECISIONS.md)).

**Producción:** nginx sirve `src/`, `styles/`, `assets/` y `uploads/`; todo lo demás (API y
páginas HTML) pasa a gunicorn. Ver [Deployment](#deployment-producción).

---

## Crear un administrador

```bash
cd backend
python manage.py create-admin
# o sin interacción:
ADMIN_PASSWORD='UnaClaveSegura123' python manage.py create-admin --email admin@tutienda.com --first-name Ana --last-name López
```

Con Docker: `docker compose exec app python manage.py create-admin`.

Roles incluidos: **Cliente**, **Administrador** (todos los permisos) y **Encargado de
inventario** (ejemplo de rol limitado). Para agregar un rol o permiso, edita `ROLES` y
`PERMISSIONS` en `backend/app/db/migrate.py` y ejecuta `migrate`. El rol de un usuario se cambia
en *Panel > Clientes y usuarios*.

---

## Pruebas

```bash
cd backend
python -m unittest discover -s tests -t .      # 69 pruebas, ~15 s
# Sobre PostgreSQL (base exclusiva de pruebas; se borra en cada prueba):
TEST_DATABASE_URL=postgresql://usuario:clave@localhost:5432/tienda_test python -m unittest discover -s tests -t .
# o, si instalaste pytest:
pytest -q tests
```

Cubren registro, login, bloqueo por fuerza bruta, recuperación de contraseña, sesiones, CSRF,
cabeceras de seguridad, inyección SQL, carrito, cálculo de precios, promociones, cupones,
envíos, puntos (bloques y topes), checkout, idempotencia, inventario, estados de pedido,
cancelaciones con reversión, canje de recompensas, permisos por rol, subida de imágenes, SEO y
**concurrencia real con hilos**:

- 20 clientes comprando a la vez las últimas 5 unidades: exactamente 5 pedidos, stock 0.
- 6 envíos simultáneos del mismo pedido (doble clic): un solo pedido.
- 8 canjes simultáneos con saldo para uno: un solo canje, saldo 0.
- Cupón de 3 usos con 10 compras simultáneas: exactamente 3 usos.

**Pruebas de navegador (opcionales):** con el servidor en marcha y los datos demo cargados:

```bash
pip install playwright && playwright install chromium
python e2e/test_store_flow.py      # invitado, registro, checkout con cupón y envío, canje
python e2e/test_admin_flow.py      # panel: productos con imagen, pedidos, cupones, configuración
```

---

## Datos de demostración

`python manage.py seed-demo` crea datos **ficticios** para probar todos los flujos:

- 6 categorías y 16 productos con "(demo)" en el nombre, SKU `DEMO-###`, marca `is_demo` e
  imágenes rotuladas "Imagen de prueba". En la tienda muestran la etiqueta *Dato de prueba*,
  no aparecen en el sitemap y llevan `noindex`.
- Usuarios con dominio reservado `example.com`:
  - `admin.demo@example.com` / `AdminDemo123`
  - `cliente.demo@example.com` / `ClienteDemo123` (1,500 puntos de prueba)
- Cupón `DEMO10` (10 % desde Q100), una promoción del 15 % en una categoría y 3 recompensas.

El comando se niega a ejecutarse en producción salvo con `--force`. Para eliminar los datos
demo antes de publicar:

```sql
DELETE FROM products WHERE is_demo = TRUE;          -- los que tengan ventas: archivar desde el panel
DELETE FROM users WHERE email LIKE '%@example.com';
DELETE FROM categories WHERE name LIKE '%(demo)';
DELETE FROM coupons WHERE code = 'DEMO10';
```

---

## Deployment (producción)

### Opción A: Docker Compose (recomendada para empezar)

```bash
cp .env.example .env
# Editar .env: APP_ENV=production, SECRET_KEY, POSTGRES_PASSWORD, PUBLIC_BASE_URL=https://tudominio.com
docker compose up -d --build
docker compose exec app python manage.py create-admin
```

Levanta PostgreSQL, la aplicación (gunicorn; aplica migraciones al arrancar) y nginx en el
puerto 80. Configura HTTPS con un certificado (por ejemplo, certbot en nginx o el balanceador
de tu proveedor). Con HTTPS activo, las cookies son `Secure` y se envía HSTS.

### Opción B: servidor o plataforma propia

1. PostgreSQL 14+ y Python 3.11+.
2. `pip install -r backend/requirements.txt`
3. Variables de entorno de producción (ver tabla).
4. `python manage.py migrate`
5. `gunicorn wsgi:app --workers 3 --threads 4 --bind 0.0.0.0:8000` (desde `backend/`).
6. Proxy inverso con [`deploy/nginx.conf`](deploy/nginx.conf) como base.
7. `UPLOAD_DIR` en un volumen persistente (o implementar almacenamiento S3, ver
   `services/storage_service.py`).

### Lista de verificación antes de publicar

- [ ] `APP_ENV=production`, `SECRET_KEY` aleatoria, PostgreSQL, HTTPS.
- [ ] Datos demo eliminados; productos, categorías y textos legales reales.
- [ ] Nombre, logo, colores, contacto y redes en *Panel > Configuración*.
- [ ] Reglas de puntos y recompensas revisadas en *Panel > Fidelización*.
- [ ] Métodos de entrega y costos reales.
- [ ] Proveedor de correo implementado (hoy los correos se escriben en el log).
- [ ] Copias de seguridad automáticas de PostgreSQL y del volumen de imágenes.
- [ ] Pooler de conexiones (PgBouncer) si se espera tráfico alto.

---

## Qué está pendiente de definir

| Tema | Estado actual | Cómo completarlo |
|---|---|---|
| Productos reales | Datos demo marcados | Cargar desde el panel |
| Logo y colores | Nombre y paleta provisional | *Panel > Configuración* |
| Contacto y redes | Vacíos | *Panel > Configuración* |
| Pago con tarjeta | Arquitectura lista; contra entrega y transferencia activos | Implementar un proveedor en `backend/app/payments/providers/` (ver docs/DECISIONS.md) |
| Empresa de envíos | Métodos y costos configurables | *Panel > Configuración*; integración futura como servicio |
| Correo transaccional | Se registra en el log | Implementar un backend en `notification_service.py` |
| Textos legales | Marcador de posición visible | Reemplazar en `frontend/src/pages/legal.js` |
| Código QR en la tarjeta | La tarjeta muestra número e ID de cliente | Agregar generador QR si se usará en tienda física |

---

## Documentación técnica

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md): capas, flujo de una compra, modelo de datos, escalabilidad.
- [docs/DECISIONS.md](docs/DECISIONS.md): decisiones técnicas y sus alternativas.
- [docs/API.md](docs/API.md): referencia de endpoints.
- [docs/SECURITY.md](docs/SECURITY.md): medidas de seguridad y cómo se prueban.
