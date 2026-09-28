import { html, render, $ } from '../../utils/html.js';
import { api } from '../../services/api.js';
import { money, number, plural } from '../../utils/format.js';
import { kpi, pageHead } from '../ui.js';

const LABEL = { pending: 'Pendientes', paid: 'Pagados', preparing: 'Preparando', shipped: 'Enviados', delivered: 'Entregados', cancelled: 'Cancelados' };

export default async function dashboard(el, { query }) {
  const days = [7, 30, 90].includes(+query.get('dias')) ? +query.get('dias') : 30;
  const s = await api.get('/admin/stats', { days });
  const max = Math.max(1, ...s.daily.map((d) => d.revenue_cents));
  render(el, html`
    ${pageHead('Resumen', html`<nav class="seg" aria-label="Periodo">${[7, 30, 90].map((d) => html`<a href="/admin?dias=${d}" ${d === days ? html`aria-current="page"` : ''}>${d} días</a>`)}</nav>`)}
    <section class="kpis" aria-label="Indicadores">
      ${kpi('Ingresos', money(s.sales.revenue_cents), `${plural(s.sales.orders, 'pedido', 'pedidos')} sin cancelar`)}
      ${kpi('Ticket promedio', money(s.sales.avg_ticket_cents))}
      ${kpi('Clientes nuevos', number(s.new_users), `${number(s.total_users)} en total`)}
      ${kpi('Puntos usados', number(s.sales.points_used), `${number(s.points_outstanding)} puntos por canjear`)}
    </section>
    <div class="a-grid">
      <section class="a-card" aria-labelledby="h-daily">
        <h2 id="h-daily" class="a-card__title">Ingresos por día</h2>
        ${s.daily.length ? html`<ol class="bars">${s.daily.map((d) => html`
          <li><span class="bars__day">${d.day.slice(5)}</span><span class="bars__track"><span class="bars__fill" data-w="${Math.round((d.revenue_cents / max) * 100)}"></span></span><span class="bars__val">${money(d.revenue_cents)}</span></li>`)}</ol>`
          : html`<p class="muted">Aún no hay ventas en este periodo.</p>`}
      </section>
      <section class="a-card" aria-labelledby="h-status">
        <h2 id="h-status" class="a-card__title">Pedidos por estado</h2>
        ${s.orders_by_status.length ? html`<dl class="kv">${s.orders_by_status.map((o) => html`<div><dt><a href="/admin/pedidos?status=${o.status}">${LABEL[o.status] || o.status}</a></dt><dd>${number(o.n)}</dd></div>`)}</dl>` : html`<p class="muted">Sin pedidos.</p>`}
      </section>
      <section class="a-card" aria-labelledby="h-top">
        <h2 id="h-top" class="a-card__title">Productos más vendidos</h2>
        ${s.top_products.length ? html`<table class="a-table"><thead><tr><th>Producto</th><th class="num">Unidades</th><th class="num">Ingresos</th></tr></thead>
          <tbody>${s.top_products.map((p) => html`<tr><td>${p.name}</td><td class="num">${number(p.units)}</td><td class="num">${money(p.revenue_cents)}</td></tr>`)}</tbody></table>` : html`<p class="muted">Sin ventas todavía.</p>`}
      </section>
      <section class="a-card" aria-labelledby="h-low">
        <h2 id="h-low" class="a-card__title">Poco stock</h2>
        ${s.low_stock.length ? html`<table class="a-table"><thead><tr><th>Producto</th><th>SKU</th><th class="num">Stock</th></tr></thead>
          <tbody>${s.low_stock.map((p) => html`<tr><td><a href="/admin/productos/${p.id}">${p.name}</a></td><td>${p.sku}</td><td class="num ${p.stock === 0 ? 'neg' : ''}">${p.stock}</td></tr>`)}</tbody></table>` : html`<p class="muted">Todo el inventario está por encima del mínimo.</p>`}
      </section>
    </div>`);
  // Ancho de barras vía CSSOM (la CSP no permite atributos style en línea).
  el.querySelectorAll('.bars__fill').forEach((b) => { b.style.width = `${b.dataset.w}%`; });
}
