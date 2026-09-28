import { html, render } from '../../utils/html.js';
import { api } from '../../services/api.js';
import { setTitle } from '../../router.js';
import { date, money, number } from '../../utils/format.js';
import { loyaltyCard } from '../../components/loyaltyCard.js';
import { pagination } from '../../components/pagination.js';
import { accountLayout, bindLayout } from './layout.js';

const STATUS = { pending: 'Pendiente', posted: 'Acreditado', cancelled: 'Anulado' };

export default async function points(el, ctx) {
  setTitle('Puntos y tarjeta');
  const page = parseInt(ctx.query.get('page') || '1', 10) || 1;
  const [card, moves, coupons] = await Promise.all([
    api.get('/loyalty/card'), api.get('/loyalty/movements', { page, page_size: 15 }), api.get('/loyalty/coupons')]);
  render(el, accountLayout('/cuenta/puntos', 'Puntos y tarjeta', html`
    <div class="points-top">
      ${loyaltyCard(card)}
      <dl class="stat-list">
        <div><dt>Disponibles</dt><dd>${number(card.points_available)}</dd></div>
        <div><dt>Pendientes</dt><dd>${number(card.points_pending)}</dd></div>
        <div><dt>Ganados en total</dt><dd>${number(card.points_earned)}</dd></div>
        <div><dt>Utilizados</dt><dd>${number(card.points_used)}</dd></div>
      </dl>
    </div>
    <p class="muted">Ganas ${number(card.earn_rule.points_per_currency_unit)} ${card.earn_rule.points_per_currency_unit === 1 ? 'punto' : 'puntos'} por cada ${money(100)} de compra. Los puntos quedan pendientes hasta que tu pedido se entrega. ${number(card.redeem_rule.points)} puntos = ${money(card.redeem_rule.value_cents)}.</p>
    <p><a class="btn btn--brass" href="/recompensas" data-link>Canjear recompensas</a></p>
    ${coupons.items.length ? html`
    <section aria-labelledby="h-coupons"><h2 id="h-coupons" class="section__title">Mis cupones de recompensa</h2>
      <ul class="coupon-list">${coupons.items.map((c) => html`<li class="${c.used || c.expired ? 'is-used' : ''}">
        <span class="coupon-code">${c.code}</span><span>${c.description}</span>
        <span class="muted">${c.used ? 'Usado' : c.expired ? 'Vencido' : `Válido hasta ${date(c.ends_at)}`}</span></li>`)}</ul></section>` : ''}
    <section aria-labelledby="h-moves">
      <h2 id="h-moves" class="section__title">Movimientos</h2>
      ${moves.items.length ? html`<table class="table"><thead><tr><th scope="col">Fecha</th><th scope="col">Detalle</th><th scope="col">Estado</th><th scope="col" class="num">Puntos</th></tr></thead>
        <tbody>${moves.items.map((m) => html`<tr>
          <td>${date(m.created_at)}</td><td>${m.description}${m.order_number ? html` <small class="muted">(${m.order_number})</small>` : ""}</td><td>${STATUS[m.status] || m.status}</td>
          <td class="num ${m.points < 0 ? 'neg' : 'pos'}">${m.points > 0 ? '+' : ''}${number(m.points)}</td></tr>`)}</tbody></table>
        ${pagination(moves.pagination, (n) => `/cuenta/puntos?page=${n}`)}` : html`<p class="muted">Todavía no tienes movimientos.</p>`}
    </section>`));
  bindLayout(el);
}
