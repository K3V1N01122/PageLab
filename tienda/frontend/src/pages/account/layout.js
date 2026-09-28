import { html } from '../../utils/html.js';

const LINKS = [
  ['/cuenta', 'Resumen'], ['/cuenta/pedidos', 'Pedidos'], ['/cuenta/puntos', 'Puntos y tarjeta'],
  ['/cuenta/favoritos', 'Favoritos'], ['/cuenta/perfil', 'Datos personales'], ['/cuenta/direcciones', 'Direcciones'],
  ['/cuenta/seguridad', 'Seguridad'],
];

export const accountLayout = (active, title, body) => html`
  <div class="container account">
    <nav class="account__nav" aria-label="Mi cuenta"><ul>
      ${LINKS.map(([href, label]) => html`<li><a href="${href}" data-link ${href === active ? html`aria-current="page"` : ''}>${label}</a></li>`)}
      <li><button type="button" class="linklike" data-logout>Cerrar sesión</button></li>
    </ul></nav>
    <div class="account__content">
      <h1 class="page-title">${title}</h1>
      ${body}
    </div>
  </div>`;

export function bindLayout(el) {
  el.querySelector('[data-logout]')?.addEventListener('click', async () => {
    const { auth } = await import('../../services/auth.js');
    const { navigate } = await import('../../router.js');
    await auth.logout();
    navigate('/', { replace: true });
  });
}

export const statusPill = (status, label) => html`<span class="pill pill--${status}">${label}</span>`;
