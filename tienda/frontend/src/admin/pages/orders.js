import { html, render, $ } from '../../utils/html.js';
import { api } from '../../services/api.js';
import { dateTime, money, number } from '../../utils/format.js';
import { pagination } from '../../components/pagination.js';
import { toast, toastError } from '../../components/toast.js';
import { statusPill } from '../../pages/account/layout.js';
import { go, can } from '../main.js';
import { pageHead } from '../ui.js';
import { store } from '../../store/store.js';

const PAY_STATUS = { pending: 'pendiente', paid: 'pagado', failed: 'rechazado', cancelled: 'cancelado', refund_due: 'reembolso pendiente' };

export default async function orders(el, ctx) {
  if (ctx.sub[0]) return detail(el, parseInt(ctx.sub[0], 10));
  const q = ctx.query;
  const page = parseInt(q.get('page') || '1', 10) || 1;
  const [{ items: statuses }, data] = await Promise.all([
    api.get('/admin/orders/statuses'),
    api.get('/admin/orders', { page, q: q.get('q'), status: q.get('status'), from: q.get('from'), to: q.get('to') })]);
  render(el, html`
    ${pageHead('Pedidos')}
    <form class="a-filters" data-filters role="search">
      <div class="field"><label for="q">Buscar</label><input id="q" name="q" type="search" value="${q.get('q') || ''}" placeholder="Número, cliente o correo"></div>
      <div class="field"><label for="status">Estado</label><select id="status" name="status"><option value="">Todos</option>
        ${statuses.map((s) => html`<option value="${s.code}" ${s.code === q.get('status') ? 'selected' : ''}>${s.label}</option>`)}</select></div>
      <div class="field"><label for="from">Desde</label><input id="from" name="from" type="date" value="${q.get('from') || ''}"></div>
      <div class="field"><label for="to">Hasta</label><input id="to" name="to" type="date" value="${q.get('to') || ''}"></div>
      <button class="btn btn--primary" type="submit">Filtrar</button>
    </form>
    <p class="muted">${number(data.pagination.total)} pedidos</p>
    ${data.items.length ? html`<div class="table-wrap"><table class="a-table">
      <thead><tr><th>Pedido</th><th>Fecha</th><th>Cliente</th><th>Estado</th><th>Pago</th><th class="num">Total</th></tr></thead>
      <tbody>${data.items.map((o) => html`<tr>
        <td><a href="/admin/pedidos/${o.id}">${o.order_number}</a></td><td>${dateTime(o.created_at)}</td>
        <td>${o.customer_name}<br><small class="muted">${o.customer_email}</small></td>
        <td>${statusPill(o.status, o.status_label)}</td><td>${o.payment_status === 'paid' ? 'Pagado' : 'Pendiente'}</td>
        <td class="num">${money(o.total_cents)}</td></tr>`)}</tbody></table></div>
      ${pagination(data.pagination, (n) => { const p = new URLSearchParams(location.search); p.set('page', n); return `/admin/pedidos?${p}`; })}`
      : html`<p class="state">No hay pedidos con estos filtros.</p>`}`);
  $('[data-filters]', el).addEventListener('submit', (e) => {
    e.preventDefault();
    const p = new URLSearchParams([...new FormData(e.target)].filter(([, v]) => v));
    go(`/admin/pedidos?${p}`);
  });
}

async function detail(el, id) {
  const [o, meta] = await Promise.all([api.get(`/admin/orders/${id}`), api.get('/admin/orders/statuses')]);
  const order = Object.fromEntries(meta.items.map((s) => [s.code, s.sort_order]));
  const next = [...(meta.transitions[o.status] || [])].sort((a, b) => order[a] - order[b]);
  const labels = Object.fromEntries(meta.items.map((s) => [s.code, s.label]));
  const a = o.shipping_address;
  const cfg = store.get().config || {};
  const shipLabel = (cfg.shipping_methods || []).find((m) => m.code === o.shipping_method)?.label || o.shipping_method;
  const payLabel = (cfg.payment_providers || []).find((p) => p.code === o.payment_provider)?.label || o.payment_provider;
  render(el, html`
    ${pageHead(`Pedido ${o.order_number}`, html`<a class="btn btn--ghost" href="/admin/pedidos">Volver a pedidos</a>`)}
    <p>${statusPill(o.status, o.status_label)} <span class="muted">Creado el ${dateTime(o.created_at)}</span></p>
    <div class="a-grid">
      <section class="a-card"><h2 class="a-card__title">Productos</h2>
        <table class="a-table"><thead><tr><th>Producto</th><th>SKU</th><th class="num">Cant.</th><th class="num">Precio</th><th class="num">Total</th></tr></thead>
          <tbody>${o.items.map((i) => html`<tr><td>${i.product_name}</td><td>${i.sku}</td><td class="num">${i.quantity}</td><td class="num">${money(i.unit_price_cents)}</td><td class="num">${money(i.line_total_cents)}</td></tr>`)}</tbody></table>
        <dl class="kv">
          <div><dt>Subtotal</dt><dd>${money(o.subtotal_cents)}</dd></div>
          <div><dt>Descuento${o.coupon_code ? ` (${o.coupon_code})` : ''}</dt><dd>−${money(o.discount_cents)}</dd></div>
          <div><dt>Puntos usados (${number(o.points_used)})</dt><dd>−${money(o.points_discount_cents)}</dd></div>
          <div><dt>Envío</dt><dd>${money(o.shipping_cents)}</dd></div>
          <div class="kv__total"><dt>Total</dt><dd>${money(o.total_cents)}</dd></div>
          <div><dt>Puntos generados</dt><dd>${number(o.points_earned)}</dd></div>
        </dl></section>
      <section class="a-card"><h2 class="a-card__title">Cliente y entrega</h2>
        <dl class="kv kv--stack">
          <div><dt>Cliente</dt><dd>${o.customer_name}<br>${o.customer_email}${o.customer_phone ? html`<br>${o.customer_phone}` : ''}</dd></div>
          <div><dt>Entrega</dt><dd>${shipLabel}</dd></div>
          ${a ? html`<div><dt>Dirección</dt><dd>${a.recipient}, ${a.phone}<br>${a.line1}${a.line2 ? `, ${a.line2}` : ''}<br>${a.city}${a.state ? `, ${a.state}` : ''}${a.notes ? html`<br>${a.notes}` : ''}</dd></div>` : ''}
          <div><dt>Pago</dt><dd>${payLabel}: ${PAY_STATUS[o.payment_status === 'paid' ? 'paid' : o.payment?.status || 'pending'] || o.payment?.status}</dd></div>
          ${o.notes ? html`<div><dt>Notas del cliente</dt><dd>${o.notes}</dd></div>` : ''}
        </dl>
        ${can('orders.update') && next.length ? html`
        <form class="a-status" data-status>
          <h3 class="a-card__title">Cambiar estado</h3>
          <div class="field"><label for="to">Nuevo estado</label><select id="to" name="status">${next.map((s) => html`<option value="${s}">${labels[s]}</option>`)}</select></div>
          <div class="field"><label for="note">Nota interna <span class="optional">(opcional)</span></label><input id="note" name="note" maxlength="300"></div>
          <button class="btn btn--primary" type="submit">Actualizar estado</button>
          <p class="help">Cancelar devuelve el stock, los puntos usados y libera el cupón.</p>
        </form>` : ''}
        <h3 class="a-card__title">Historial</h3>
        <ol class="timeline">${o.history.map((h) => html`<li><strong>${h.to_label}</strong><span class="muted">${dateTime(h.created_at)}</span>${h.note ? html`<span>${h.note}</span>` : ''}</li>`)}</ol>
      </section>
    </div>`);
  $('[data-status]', el)?.addEventListener('submit', async (e) => {
    e.preventDefault();
    const f = e.target;
    if (f.status.value === 'cancelled' && !confirm('¿Cancelar este pedido?')) return;
    f.querySelector('button').disabled = true;
    try { await api.post(`/admin/orders/${id}/status`, { status: f.status.value, note: f.note.value || null }); toast('Estado actualizado.'); detail(el, id); }
    catch (err) { toastError(err); f.querySelector('button').disabled = false; }
  });
}
