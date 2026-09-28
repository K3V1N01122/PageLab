import { html, render } from '../utils/html.js';
import { setTitle } from '../router.js';

export default async function notFound(el) {
  setTitle('Página no encontrada');
  render(el, html`
    <div class="container narrow status-page">
      <p class="status-page__code" aria-hidden="true">404</p>
      <h1 class="page-title">No encontramos esta página</h1>
      <p class="page-lead">Es posible que el enlace esté mal escrito o que el producto ya no esté disponible.</p>
      <div class="hero__actions"><a class="btn btn--primary" href="/catalogo" data-link>Ver catálogo</a><a class="btn btn--ghost" href="/" data-link>Ir al inicio</a></div>
    </div>`);
}
