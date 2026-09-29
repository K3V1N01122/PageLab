# Publicar la demo gratis (Render + Neon)

Guía para poner la tienda de **demostración** en internet sin pagar ni comprar dominio.
Resultado: una dirección como `https://pagelab-demo.onrender.com` que abre en cualquier
celular.

| Pieza | Servicio gratuito | Para qué |
|---|---|---|
| Página (la aplicación) | **Render** (plan Free) | Ejecuta la tienda desde tu repositorio de GitHub |
| Base de datos | **Neon** (plan Free) | PostgreSQL que no se borra |

## Limitaciones del plan gratuito (importante)

- **Se duerme tras 15 minutos sin visitas.** La primera visita después tarda cerca de 1 minuto
  en cargar. Antes de mostrarla a un cliente, ábrela un minuto antes.
- **Correos:** Render Free bloquea los puertos de correo (SMTP), así que Gmail no envía desde
  la demo publicada. En tu computadora siguen funcionando.
- **Imágenes subidas desde el panel:** el disco de Render Free se borra en cada reinicio. Las
  imágenes de los productos demo se regeneran solas; las que subas tú se perderían.
- Es para **mostrar**, no para una tienda real. Una tienda real usa un plan de pago.

## 1. Base de datos en Neon

1. Entra a <https://neon.tech> y regístrate con tu cuenta de GitHub.
2. Crea un proyecto: nombre `pagelab`, región **AWS US East (N. Virginia)**.
3. En el panel del proyecto pulsa **Connect** y copia la **cadena de conexión**. Empieza con
   `postgresql://` y termina con algo como `?sslmode=require`.
   Guárdala: es una contraseña. No la compartas ni la subas a GitHub.

## 2. Página en Render

1. Entra a <https://render.com> y regístrate con tu cuenta de GitHub.
2. **New → Web Service** y conecta el repositorio **PageLab** (autoriza el acceso si lo pide).
3. Configura:
   - **Name:** `pagelab-demo` (define la dirección: `https://pagelab-demo.onrender.com`).
   - **Region:** Virginia (US East), la misma de Neon.
   - **Root Directory:** `tienda`
   - **Language / Runtime:** Docker
   - **Instance Type:** Free
4. En **Environment Variables** agrega:

| Variable | Valor |
|---|---|
| `APP_ENV` | `production` |
| `SECRET_KEY` | Una clave larga aleatoria (ver abajo) |
| `DATABASE_URL` | La cadena de conexión de Neon |
| `PUBLIC_BASE_URL` | `https://pagelab-demo.onrender.com` (tu dirección real, sin `/` al final) |
| `SERVE_FRONTEND` | `true` |
| `TRUST_PROXY_HEADERS` | `true` |
| `DEMO_MODE` | `true` |
| `PAYMENT_PROVIDERS` | `cash_on_delivery,bank_transfer,card_demo` |
| `DEMO_ADMIN_PASSWORD` | Una contraseña tuya para el admin demo |
| `MAIL_BACKEND` | `console` |

   Para generar la `SECRET_KEY`, en tu terminal (con el entorno activado):
   ```
   python -c "import secrets; print(secrets.token_urlsafe(48))"
   ```
5. Pulsa **Create Web Service**. La primera vez tarda entre 5 y 10 minutos. Cuando diga
   **Live**, abre la dirección.

Al arrancar, la tienda crea las tablas y carga los datos demo automáticamente.
El panel está en `/admin` con `admin.demo@example.com` y tu `DEMO_ADMIN_PASSWORD`.

## 3. Actualizar la demo

Cada vez que hagas **Commit** y **Sync Changes** en VS Code, Render vuelve a publicar la tienda
sola en unos minutos. Los datos (pedidos, configuración) se conservan en Neon.

## Si algo falla

En Render abre tu servicio → **Logs**. Los errores más comunes:

| Mensaje | Solución |
|---|---|
| `SECRET_KEY debe definirse en producción` | Falta `SECRET_KEY` o tiene menos de 32 caracteres. |
| `En producción use PostgreSQL` | `DATABASE_URL` vacía o mal copiada. |
| `card_demo … solo se permite con DEMO_MODE=true` | Agrega `DEMO_MODE=true`. |
| «La sesión del formulario expiró» al iniciar sesión | `PUBLIC_BASE_URL` no coincide con la dirección real (revisa `https` y el nombre). |
