# Decisiones técnicas

Cada decisión incluye la alternativa considerada, para que el equipo pueda revisarla si
cambian las necesidades.

### 1. Flask + SQL explícito en lugar de un framework con ORM
Las operaciones críticas (stock, puntos, cupones) dependen de sentencias exactas como
`UPDATE ... WHERE stock >= ?`. Con SQL explícito se ve y se prueba exactamente qué se ejecuta.
Todas las consultas usan parámetros (`?`), nunca concatenación.
*Alternativa:* Django o SQLAlchemy. Aportan admin y migraciones automáticas, a cambio de más
dependencias y abstracción. Migrar sería viable porque la lógica está aislada en `services/`.

### 2. PostgreSQL en producción, SQLite en desarrollo
El mismo SQL corre en ambos (traducción de parámetros y tipos en `db/`). SQLite permite
instalar y probar sin servicios externos; PostgreSQL da concurrencia real y robustez.
**Limitación honesta:** la batería de pruebas se ejecutó sobre SQLite (incluida la
concurrencia) porque el entorno de desarrollo no tenía PostgreSQL. Antes de producción,
ejecútala contra una base PostgreSQL **exclusiva para pruebas** (se borra en cada prueba):
`TEST_DATABASE_URL=postgresql://usuario:clave@localhost:5432/tienda_test python -m unittest discover -s tests -t .` El código usa solo SQL
estándar compatible (`RETURNING`, `ON CONFLICT`, savepoints).

### 3. Sesiones opacas en base de datos en lugar de JWT
El token es aleatorio (256 bits) y en la base se guarda solo su hash. Permite cerrar sesión de
verdad, revocar todas las sesiones al cambiar la contraseña o el rol, y desactivar cuentas al
instante. Un JWT no se puede revocar sin una lista negra.
Navegador: cookie `HttpOnly`, `SameSite=Lax`, `Secure` en producción.
Apps: el mismo token por `Authorization: Bearer`.

### 4. Frontend sin framework ni compilación
Módulos ES nativos, un router propio y plantillas con escape automático (`utils/html.js`).
Cero dependencias que actualizar y ningún paso de build que pueda romperse.
*Alternativa:* React/Vue + Vite. Tiene sentido si el equipo ya lo usa o si la interfaz crece
mucho; la API no cambiaría. Los módulos están organizados como componentes para facilitarlo.

### 5. SEO con metadatos del servidor sobre una SPA
El backend inserta título, descripción, Open Graph, canonical y JSON-LD (Product/Store) en el
HTML de cada URL, y responde 404 reales para rutas o productos inexistentes. Así se obtiene
buen SEO sin renderizar toda la página en el servidor.
*Siguiente paso posible:* renderizado en servidor del listado de productos para buscadores.

### 6. Pagos: interfaz de proveedores
`PaymentProvider` define `create_payment` y `handle_webhook`. Incluidos: **contra entrega**,
**transferencia** y **tarjeta de prueba** (solo desarrollo; la configuración de producción la
rechaza). Para integrar un proveedor real (Stripe, PayPal o una pasarela local):
1. Crear `payments/providers/<codigo>.py` (claves desde variables de entorno).
2. Registrarlo en `payments/registry.py`.
3. Agregar una ruta de webhook que llame a `handle_webhook`, verifique la firma y marque el
   pedido como pagado con `order_service.change_status(..., "paid")`.
4. Habilitarlo en `PAYMENT_PROVIDERS`.

### 7. Puntos pendientes hasta la entrega
Evita que alguien compre, gane puntos, los canjee y luego cancele. El estado que acredita es
configurable (`paid` o `delivered`). Los puntos se canjean en bloques (1,000 = Q50 por defecto)
con un tope porcentual por compra (50 % por defecto) para proteger el margen.

### 8. Recompensas como cupones personales
Canjear una recompensa descuenta los puntos y genera un cupón de un solo uso ligado a la
cuenta. Así todas las recompensas pasan por el mismo motor de precios y validaciones.

### 9. Promociones automáticas no acumulables
Si varias aplican, se usa la mayor. Los cupones sí se suman a la promoción. El ordenamiento
por precio del catálogo usa el precio base (sin promociones) para mantener la consulta
indexada; documentado como compromiso aceptable.

### 10. Rate limiting en la base de datos
Funciona con varias instancias sin servicios extra. Con mucho tráfico, cambiar a Redis
reimplementando una sola función (`core/ratelimit._hit`).

### 11. Carrito de invitado en el navegador
El invitado guarda solo IDs y cantidades (nunca precios) en `localStorage`. Al iniciar sesión
se fusiona con el carrito del servidor ajustando al stock disponible. El checkout requiere
cuenta porque los puntos y el historial dependen de ella.

### 12. Correo
El proveedor no está definido. El backend `console` escribe los correos en el log; un fallo de
correo nunca interrumpe una compra.

### 13. Tipografía y diseño
Paleta fría (tinta, papel, jade para acciones y latón exclusivo del programa de puntos) y una
sola familia tipográfica (Schibsted Grotesk, con respaldo del sistema). El elemento con más
personalidad es la tarjeta de fidelidad. Los colores principales se cambian desde el panel sin
tocar código. Si la tienda prefiere no depender de Google Fonts, basta con alojar la fuente en
`assets/` y ajustar `index.html` y la CSP.
