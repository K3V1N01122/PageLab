import { html, render } from '../utils/html.js';
import { api } from '../services/api.js';
import { setTitle } from '../router.js';
import { money, number } from '../utils/format.js';

export default async function orderConfirm(el, ctx) {
  const o = await api.get(`/account/orders/${encodeURIComponent(ctx.params.number)}`);
  setTitle(`Pedido ${o.order_number}`);
  render(el, html`
    <div class="container narrow confirm">
      <h1 class="page-title">Recibimos tu pedido</h1>
      <p class="page-lead">Tu número de pedido es <strong>${o.order_number}</strong>. Te enviamos la confirmación a ${o.customer_email}.</p>
      ${o.payment?.card ? html`<div class="notice notice--success"><p>Pago aprobado con ${o.payment.card.brand} terminada en ${o.payment.card.last4}${o.payment.card.demo ? ' (modo demostración, sin cobro real)' : ''}.</p></div>` : ''}
      ${o.payment?.instructions ? html`<div class="notice notice--info"><p>${o.payment.instructions}</p></div>` : ''}
      <dl class="totals">
        <div><dt>Estado</dt><dd>${o.status_label}</dd></div>
        <div><dt>Total</dt><dd>${money(o.total_cents)}</dd></div>
        ${o.points_earned ? html`<div class="totals__earn"><dt>Puntos por acreditar</dt><dd>${number(o.points_earned)}</dd></div>` : ''}
      </dl>
      <div class="hero__actions">
        <a class="btn btn--primary" href="/cuenta/pedidos/${o.order_number}" data-link>Ver detalle del pedido</a>
        <a class="btn btn--ghost" href="/catalogo" data-link>Seguir comprando</a>
      </div>
    </div>`);
}
