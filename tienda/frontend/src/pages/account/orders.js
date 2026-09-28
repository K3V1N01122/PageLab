import { html, render } from '../../utils/html.js';
import { api } from '../../services/api.js';
import { setTitle } from '../../router.js';
import { date, money, plural } from '../../utils/format.js';
import { pagination } from '../../components/pagination.js';
import { empty } from '../../components/states.js';
import { accountLayout, bindLayout, statusPill } from './layout.js';

const TABS = [['current', 'En curso'], ['past', 'Anteriores'], ['all', 'Todos']];

export default async function orders(el, ctx) {
  setTitle('Mis pedidos');
  const scope = TABS.some(([k]) => k === ctx.query.get('ver')) ? ctx.query.get('ver') : 'all';
  const page = parseInt(ctx.query.get('page') || '1', 10) || 1;
  const data = await api.get('/account/orders', { scope, page, page_size: 10 });
  render(el, accountLayout('/cuenta/pedidos', 'Mis pedidos', html`
    <nav class="tabs" aria-label="Filtrar pedidos">${TABS.map(([k, l]) => html`
      <a href="/cuenta/pedidos?ver=${k}" data-link ${k === scope ? html`aria-current="page"` : ''}>${l}</a>`)}</nav>
    ${data.items.length ? html`
      <ul class="order-list">${data.items.map((o) => html`
        <li><a href="/cuenta/pedidos/${o.order_number}" data-link class="order-row">
          <span class="order-row__num">${o.order_number}</span>
          <span>${date(o.created_at)}</span>
          <span>${plural(o.item_count, 'producto', 'productos')}</span>
          ${statusPill(o.status, o.status_label)}
          <span class="order-row__total">${money(o.total_cents)}</span>
        </a></li>`)}</ul>
      ${pagination(data.pagination, (n) => `/cuenta/pedidos?ver=${scope}&page=${n}`)}`
      : empty('No hay pedidos aquí', 'Cuando compres, verás tus pedidos en esta sección.', { href: '/catalogo', label: 'Ver catálogo' })}`));
  bindLayout(el);
}
