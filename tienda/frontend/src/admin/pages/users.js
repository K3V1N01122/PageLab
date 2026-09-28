import { html, render, $ } from '../../utils/html.js';
import { api } from '../../services/api.js';
import { date, dateTime, money, number } from '../../utils/format.js';
import { pagination } from '../../components/pagination.js';
import { toast, toastError } from '../../components/toast.js';
import { statusPill } from '../../pages/account/layout.js';
import { formData, showErrors } from '../../utils/forms.js';
import { go, can } from '../main.js';
import { pageHead } from '../ui.js';

export default async function users(el, ctx) {
  if (ctx.sub[0]) return detail(el, parseInt(ctx.sub[0], 10));
  const q = ctx.query;
  const page = parseInt(q.get('page') || '1', 10) || 1;
  const [data, { items: roles }] = await Promise.all([api.get('/admin/users', { page, q: q.get('q'), role: q.get('role') }), api.get('/admin/roles')]);
  render(el, html`
    ${pageHead('Clientes y usuarios')}
    <form class="a-filters" data-filters role="search">
      <div class="field"><label for="q">Buscar</label><input id="q" name="q" type="search" value="${q.get('q') || ''}" placeholder="Nombre, correo o ID de cliente"></div>
      <div class="field"><label for="role">Rol</label><select id="role" name="role"><option value="">Todos</option>${roles.map((r) => html`<option value="${r.code}" ${r.code === q.get('role') ? 'selected' : ''}>${r.name}</option>`)}</select></div>
      <button class="btn btn--primary" type="submit">Filtrar</button>
    </form>
    <p class="muted">${number(data.pagination.total)} usuarios</p>
    <div class="table-wrap"><table class="a-table">
      <thead><tr><th>Nombre</th><th>Correo</th><th>Rol</th><th class="num">Pedidos</th><th class="num">Puntos</th><th>Registro</th><th>Estado</th></tr></thead>
      <tbody>${data.items.map((u) => html`<tr>
        <td><a href="/admin/usuarios/${u.id}">${u.first_name} ${u.last_name}</a><br><small class="muted">${u.public_id}</small></td>
        <td>${u.email}</td><td>${u.role_name}</td><td class="num">${u.order_count}</td><td class="num">${number(u.points_balance)}</td>
        <td>${date(u.created_at)}</td><td>${u.is_active ? 'Activo' : html`<span class="neg">Desactivado</span>`}</td></tr>`)}</tbody>
    </table></div>
    ${pagination(data.pagination, (n) => { const p = new URLSearchParams(location.search); p.set('page', n); return `/admin/usuarios?${p}`; })}`);
  $('[data-filters]', el).addEventListener('submit', (e) => {
    e.preventDefault();
    go(`/admin/usuarios?${new URLSearchParams([...new FormData(e.target)].filter(([, v]) => v))}`);
  });
}

async function detail(el, id) {
  const [u, { items: roles }] = await Promise.all([api.get(`/admin/users/${id}`), api.get('/admin/roles')]);
  const me = (await import('../../store/store.js')).store.get().user;
  const self = me.id === u.public_id;
  const l = u.loyalty;
  render(el, html`
    ${pageHead(`${u.first_name} ${u.last_name}`, html`<a class="btn btn--ghost" href="/admin/usuarios">Volver</a>`)}
    <div class="a-grid">
      <section class="a-card"><h2 class="a-card__title">Perfil</h2>
        <dl class="kv kv--stack">
          <div><dt>ID de cliente</dt><dd>${u.public_id}</dd></div>
          <div><dt>Correo</dt><dd>${u.email}</dd></div>
          <div><dt>Teléfono</dt><dd>${u.phone || '—'}</dd></div>
          <div><dt>Registro</dt><dd>${dateTime(u.created_at)}</dd></div>
          <div><dt>Último acceso</dt><dd>${u.last_login_at ? dateTime(u.last_login_at) : 'Nunca'}</dd></div>
          <div><dt>Direcciones</dt><dd>${u.addresses.length ? u.addresses.map((a) => html`${a.recipient}: ${a.line1}, ${a.city}<br>`) : '—'}</dd></div>
        </dl>
        ${can('users.manage') ? html`
        <form data-account class="a-status">
          <h3 class="a-card__title">Cuenta</h3>
          <div class="field"><label for="role">Rol</label><select id="role" name="role" ${self ? 'disabled' : ''}>
            ${roles.map((r) => html`<option value="${r.code}" ${r.code === u.role ? 'selected' : ''}>${r.name}</option>`)}</select></div>
          <label class="check"><input type="checkbox" name="is_active" ${u.is_active ? 'checked' : ''} ${self ? 'disabled' : ''}> Cuenta activa</label>
          ${self ? html`<p class="help">No puedes cambiar tu propio rol ni desactivar tu cuenta.</p>`
            : html`<p class="help">Cambiar el rol o desactivar la cuenta cierra sus sesiones abiertas.</p><button class="btn btn--primary" type="submit">Guardar</button>`}
        </form>` : ''}
      </section>
      <section class="a-card"><h2 class="a-card__title">Fidelización</h2>
        <dl class="kv">
          <div><dt>Tarjeta</dt><dd>${l.card_number}</dd></div>
          <div><dt>Disponibles</dt><dd>${number(l.points_available)}</dd></div>
          <div><dt>Pendientes</dt><dd>${number(l.points_pending)}</dd></div>
          <div><dt>Ganados en total</dt><dd>${number(l.points_earned)}</dd></div>
          <div><dt>Utilizados</dt><dd>${number(l.points_used)}</dd></div>
        </dl>
        ${can('loyalty.manage') ? html`
        <form data-points class="a-status" novalidate>
          <h3 class="a-card__title">Ajustar puntos</h3>
          <p class="form-summary notice notice--error" role="alert" tabindex="-1" hidden></p>
          <div class="grid-2">
            <div class="field"><label for="points">Puntos</label><input id="points" name="points" type="number" step="1" data-type="int" required><p class="help">Negativo para restar.</p></div>
            <div class="field"><label for="reason">Motivo</label><input id="reason" name="reason" required maxlength="150"></div>
          </div>
          <button class="btn btn--secondary" type="submit">Aplicar ajuste</button>
        </form>` : ''}
        <h3 class="a-card__title">Últimos movimientos</h3>
        <table class="a-table"><tbody>${u.point_movements.map((m) => html`<tr><td>${date(m.created_at)}</td><td>${m.description}</td><td class="num ${m.points < 0 ? 'neg' : 'pos'}">${m.points > 0 ? '+' : ''}${number(m.points)}</td></tr>`)}</tbody></table>
      </section>
      <section class="a-card a-span"><h2 class="a-card__title">Pedidos</h2>
        ${u.orders.length ? html`<table class="a-table"><thead><tr><th>Pedido</th><th>Fecha</th><th>Estado</th><th class="num">Total</th></tr></thead>
          <tbody>${u.orders.map((o) => html`<tr><td><a href="/admin/pedidos/${o.id}">${o.order_number}</a></td><td>${date(o.created_at)}</td><td>${statusPill(o.status, o.status)}</td><td class="num">${money(o.total_cents)}</td></tr>`)}</tbody></table>`
          : html`<p class="muted">Sin pedidos.</p>`}
      </section>
    </div>`);
  $('[data-account]', el)?.addEventListener('submit', async (e) => {
    e.preventDefault();
    const d = formData(e.target);
    try { await api.patch(`/admin/users/${id}`, { role: d.role, is_active: d.is_active }); toast('Cuenta actualizada.'); detail(el, id); } catch (err) { toastError(err); }
  });
  $('[data-points]', el)?.addEventListener('submit', async (e) => {
    e.preventDefault();
    try { await api.post(`/admin/users/${id}/points`, formData(e.target)); toast('Puntos ajustados.'); detail(el, id); } catch (err) { showErrors(e.target, err); }
  });
}
