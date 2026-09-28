import { html, render } from '../../utils/html.js';
import { api } from '../../services/api.js';
import { store } from '../../store/store.js';
import { setTitle } from '../../router.js';
import { date, money } from '../../utils/format.js';
import { loyaltyCard } from '../../components/loyaltyCard.js';
import { accountLayout, bindLayout, statusPill } from './layout.js';

export default async function overview(el) {
  const user = store.get().user;
  setTitle('Mi cuenta');
  const [card, orders] = await Promise.all([api.get('/loyalty/card'), api.get('/account/orders', { scope: 'current', page_size: 5 })]);
  render(el, accountLayout('/cuenta', `Hola, ${user.first_name}`, html`
    <div class="overview">
      <div>${loyaltyCard(card)}<p><a href="/cuenta/puntos" data-link class="link-more">Ver movimientos y recompensas</a></p></div>
      <section aria-labelledby="h-current">
        <h2 id="h-current" class="section__title">Pedidos en curso</h2>
        ${orders.items.length ? html`<ul class="order-list">${orders.items.map((o) => html`
          <li><a href="/cuenta/pedidos/${o.order_number}" data-link class="order-row">
            <span class="order-row__num">${o.order_number}</span><span>${date(o.created_at)}</span>
            ${statusPill(o.status, o.status_label)}<span class="order-row__total">${money(o.total_cents)}</span></a></li>`)}</ul>`
          : html`<p class="muted">No tienes pedidos en curso. <a href="/catalogo" data-link>Ver catálogo</a></p>`}
      </section>
    </div>`));
  bindLayout(el);
}
