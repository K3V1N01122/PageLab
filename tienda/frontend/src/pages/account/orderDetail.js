import { html, render, $ } from '../../utils/html.js';
import { api } from '../../services/api.js';
import { setTitle } from '../../router.js';
import { dateTime, money, number } from '../../utils/format.js';
import { toast, toastError } from '../../components/toast.js';
import { accountLayout, bindLayout, statusPill } from './layout.js';

export default async function orderDetail(el, ctx) {
  const draw = (o) => {
    setTitle(`Pedido ${o.order_number}`);
    const a = o.shipping_address;
    render(el, accountLayout('/cuenta/pedidos', `Pedido ${o.order_number}`, html`
      <p>${statusPill(o.status, o.status_label)} <span class="muted">Realizado el ${dateTime(o.created_at)}</span></p>
      ${o.payment?.instructions && o.payment_status !== 'paid' && o.status !== 'cancelled' ? html`<div class="notice notice--info"><p>${o.payment.instructions}</p></div>` : ''}
      <div class="order-detail">
        <section aria-labelledby="h-items">
          <h2 id="h-items" class="section__title">Productos</h2>
          <table class="table"><thead><tr><th scope="col">Producto</th><th scope="col">Cantidad</th><th scope="col">Precio</th><th scope="col">Total</th></tr></thead>
            <tbody>${o.items.map((i) => html`<tr>
              <td>${i.slug ? html`<a href="/producto/${i.slug}" data-link>${i.product_name}</a>` : i.product_name}<br><small class="muted">SKU ${i.sku}</small></td>
              <td>${i.quantity}</td><td>${money(i.unit_price_cents)}</td><td>${money(i.line_total_cents)}</td></tr>`)}</tbody></table>
          <dl class="totals">
            <div><dt>Subtotal</dt><dd>${money(o.subtotal_cents)}</dd></div>
            ${o.discount_cents ? html`<div class="totals__discount"><dt>Descuento${o.coupon_code ? ` (${o.coupon_code})` : ''}</dt><dd>−${money(o.discount_cents)}</dd></div>` : ''}
            ${o.points_used ? html`<div class="totals__discount"><dt>Puntos usados (${number(o.points_used)})</dt><dd>−${money(o.points_discount_cents)}</dd></div>` : ''}
            <div><dt>Envío</dt><dd>${o.shipping_cents ? money(o.shipping_cents) : 'Gratis'}</dd></div>
            <div class="totals__total"><dt>Total</dt><dd>${money(o.total_cents)}</dd></div>
            ${o.points_earned ? html`<div class="totals__earn"><dt>Puntos generados</dt><dd>${number(o.points_earned)}</dd></div>` : ''}
          </dl>
        </section>
        <section aria-labelledby="h-ship">
          <h2 id="h-ship" class="section__title">Entrega y pago</h2>
          <dl class="facts">
            <div><dt>Método de entrega</dt><dd>${o.shipping_method === 'pickup' ? 'Recoger en tienda' : 'Envío a domicilio'}</dd></div>
            ${a ? html`<div><dt>Dirección</dt><dd>${a.recipient}, ${a.phone}<br>${a.line1}${a.line2 ? `, ${a.line2}` : ''}<br>${a.city}${a.state ? `, ${a.state}` : ''}</dd></div>` : ''}
            <div><dt>Pago</dt><dd>${o.payment_status === 'paid' ? 'Pagado' : 'Pendiente'}${o.payment?.card ? ` con ${o.payment.card.brand} •••• ${o.payment.card.last4}` : ''}</dd></div>
          </dl>
          <h2 class="section__title">Historial</h2>
          <ol class="timeline">${o.history.map((h) => html`<li><strong>${h.to_label}</strong><span class="muted">${dateTime(h.created_at)}</span>${h.note ? html`<span>${h.note}</span>` : ''}</li>`)}</ol>
          ${o.status === 'pending' ? html`<button type="button" class="btn btn--ghost danger" data-cancel>Cancelar pedido</button>` : ''}
        </section>
      </div>`));
    bindLayout(el);
    $('[data-cancel]', el)?.addEventListener('click', async (e) => {
      if (!confirm('¿Cancelar este pedido? Se devolverán los puntos usados.')) return;
      e.target.disabled = true;
      try { draw(await api.post(`/account/orders/${o.order_number}/cancel`)); toast('Pedido cancelado.'); } catch (err) { toastError(err); e.target.disabled = false; }
    });
  };
  draw(await api.get(`/account/orders/${encodeURIComponent(ctx.params.number)}`));
}
