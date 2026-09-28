import { html, render, $, $$ } from '../../utils/html.js';
import { api } from '../../services/api.js';
import { dateTime, money, number } from '../../utils/format.js';
import { formData, showErrors } from '../../utils/forms.js';
import { pagination } from '../../components/pagination.js';
import { toast, toastError } from '../../components/toast.js';
import { checkbox, dateOnly, input, intInput, moneyInput, pageHead, select, textarea } from '../ui.js';

const KINDS = [['fixed_discount', 'Descuento en quetzales'], ['percent_discount', 'Descuento porcentual'], ['free_shipping', 'Envío gratis'], ['free_product', 'Producto gratis']];

export default async function loyalty(el, ctx) {
  const page = parseInt(ctx.query.get('page') || '1', 10) || 1;
  const [settings, { items: rewards }, moves] = await Promise.all([
    api.get('/admin/loyalty/settings'), api.get('/admin/rewards'), api.get('/admin/point-movements', { page })]);
  const kindLabel = Object.fromEntries(KINDS);
  const draw = (editing = null) => {
    render(el, html`
      ${pageHead('Fidelización')}
      <div class="a-grid">
        <form class="a-card" data-settings novalidate>
          <h2 class="a-card__title">Reglas de puntos</h2>
          <p class="form-summary notice notice--error" role="alert" tabindex="-1" hidden></p>
          ${checkbox('enabled', 'Programa activo', settings.enabled)}
          ${input('program_name', 'Nombre del programa', settings.program_name)}
          ${intInput('points_per_currency_unit', 'Puntos por cada Q1 pagado', settings.points_per_currency_unit, { min: 0 })}
          <div class="grid-2">
            ${intInput('redeem_block_points', 'Canje: cada cuántos puntos', settings.redeem_block_points, { min: 1 })}
            ${moneyInput('redeem_block_value_cents', 'equivalen a (Q)', settings.redeem_block_value_cents)}
          </div>
          ${intInput('max_points_discount_percent', 'Tope de descuento con puntos (% de la compra)', settings.max_points_discount_percent, { min: 0 })}
          ${select('earn_on_status', 'Los puntos se acreditan cuando el pedido está', [['delivered', 'Entregado'], ['paid', 'Pagado']], settings.earn_on_status)}
          <button class="btn btn--primary" type="submit">Guardar reglas</button>
        </form>
        <section class="a-card">
          <div class="a-card__head"><h2 class="a-card__title">Recompensas</h2>${editing === null ? html`<button class="btn btn--secondary" type="button" data-new>Nueva recompensa</button>` : ''}</div>
          ${editing !== null ? rewardForm(editing) : ''}
          <table class="a-table"><thead><tr><th>Recompensa</th><th class="num">Puntos</th><th class="num">Canjes</th><th>Activa</th><th></th></tr></thead>
            <tbody>${rewards.map((r) => html`<tr data-id="${r.id}"><td>${r.name}<br><small class="muted">${kindLabel[r.kind]}${r.stock !== null ? `, quedan ${r.stock}` : ''}</small></td>
              <td class="num">${number(r.points_cost)}</td><td class="num">${r.redemptions}</td><td>${r.is_active ? 'Sí' : 'No'}</td>
              <td class="a-actions"><button type="button" class="linklike" data-edit>Editar</button> <button type="button" class="linklike danger" data-del>Eliminar</button></td></tr>`)}</tbody></table>
        </section>
        <section class="a-card a-span"><h2 class="a-card__title">Movimientos de puntos</h2>
          <div class="table-wrap"><table class="a-table"><thead><tr><th>Fecha</th><th>Cliente</th><th>Detalle</th><th>Estado</th><th class="num">Puntos</th></tr></thead>
            <tbody>${moves.items.map((m) => html`<tr><td>${dateTime(m.created_at)}</td><td>${m.email}<br><small class="muted">${m.public_id}</small></td><td>${m.description}</td><td>${m.status}</td>
              <td class="num ${m.points < 0 ? 'neg' : 'pos'}">${m.points > 0 ? '+' : ''}${number(m.points)}</td></tr>`)}</tbody></table></div>
          ${pagination(moves.pagination, (n) => `/admin/fidelizacion?page=${n}`)}
        </section>
      </div>`);
    bind(editing);
  };
  const rewardForm = (r) => html`
    <form class="a-subform" data-reward novalidate>
      <p class="form-summary notice notice--error" role="alert" tabindex="-1" hidden></p>
      ${input('name', 'Nombre', r.name, { required: true })}
      ${textarea('description', 'Descripción', r.description, 2)}
      <div class="grid-2">${select('kind', 'Tipo', KINDS, r.kind || 'fixed_discount')}${intInput('points_cost', 'Costo en puntos', r.points_cost, { min: 1 })}</div>
      <div class="grid-2">${moneyInput('value_cents', 'Valor (Q)', r.value_cents, { optional: true, help: 'Para descuento en quetzales.' })}${intInput('percent', 'Porcentaje', r.percent, { optional: true, min: 0 })}</div>
      <div class="grid-2">${intInput('product_id', 'ID del producto', r.product_id, { optional: true, help: 'Para producto gratis.' })}${intInput('coupon_valid_days', 'Días de validez del cupón', r.coupon_valid_days ?? 30, { min: 1 })}</div>
      <div class="grid-2">${intInput('stock', 'Existencias', r.stock, { optional: true, help: 'Vacío = ilimitado.' })}${intInput('per_user_limit', 'Límite por cliente', r.per_user_limit, { optional: true })}</div>
      <div class="grid-2">${input('starts_at', 'Inicio', dateOnly(r.starts_at), { type: 'date', optional: true })}${input('ends_at', 'Fin', dateOnly(r.ends_at), { type: 'date', optional: true })}</div>
      ${checkbox('is_active', 'Activa', r.is_active ?? true)}
      <div class="form-actions"><button class="btn btn--primary" type="submit">Guardar recompensa</button><button class="btn btn--ghost" type="button" data-cancel>Cancelar</button></div>
    </form>`;
  const bind = (editing) => {
    $('[data-settings]', el).addEventListener('submit', async (e) => {
      e.preventDefault();
      try { Object.assign(settings, await api.put('/admin/loyalty/settings', formData(e.target))); toast('Reglas guardadas.'); } catch (err) { showErrors(e.target, err); }
    });
    $('[data-new]', el)?.addEventListener('click', () => draw({}));
    $('[data-cancel]', el)?.addEventListener('click', () => draw());
    $$('[data-edit]', el).forEach((b) => b.addEventListener('click', () => draw(rewards.find((r) => r.id === +b.closest('[data-id]').dataset.id))));
    $$('[data-del]', el).forEach((b) => b.addEventListener('click', async () => {
      if (!confirm('¿Eliminar esta recompensa? Si ya tiene canjes, se desactivará.')) return;
      try { await api.del(`/admin/rewards/${b.closest('[data-id]').dataset.id}`); rewards.splice(0, rewards.length, ...(await api.get('/admin/rewards')).items); toast('Recompensa actualizada.'); draw(); } catch (err) { toastError(err); }
    }));
    const f = $('[data-reward]', el);
    f?.addEventListener('submit', async (e) => {
      e.preventDefault();
      try {
        if (editing.id) await api.put(`/admin/rewards/${editing.id}`, formData(f)); else await api.post('/admin/rewards', formData(f));
        rewards.splice(0, rewards.length, ...(await api.get('/admin/rewards')).items);
        toast('Recompensa guardada.');
        draw();
      } catch (err) { showErrors(f, err); }
    });
  };
  draw();
}
