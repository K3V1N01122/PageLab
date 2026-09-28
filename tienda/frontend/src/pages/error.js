import { html, render } from '../utils/html.js';
import { setTitle } from '../router.js';

/** Página de error genérica: nunca muestra detalles técnicos. */
export default async function errorPage(el, ctx = {}) {
  const offline = ctx.error?.code === 'network_error';
  const unauthorized = ctx.error?.status === 401;
  setTitle(offline ? 'Sin conexión' : 'Algo salió mal');
  render(el, html`
    <div class="container narrow status-page">
      <p class="status-page__code" aria-hidden="true">${offline ? '—' : '500'}</p>
      <h1 class="page-title">${offline ? 'Sin conexión con la tienda' : unauthorized ? 'Tu sesión terminó' : 'No pudimos cargar esta página'}</h1>
      <p class="page-lead">${ctx.error?.message && ctx.error?.status !== 500 ? ctx.error.message : 'Intenta de nuevo en unos momentos.'}</p>
      <div class="hero__actions">
        ${unauthorized ? html`<a class="btn btn--primary" href="/iniciar-sesion" data-link>Iniciar sesión</a>`
          : html`<a class="btn btn--primary" href="${location.pathname}${location.search}">Reintentar</a>`}
        <a class="btn btn--ghost" href="/" data-link>Ir al inicio</a>
      </div>
    </div>`);
}
