import { html, render, $, $$ } from '../../utils/html.js';
import { api } from '../../services/api.js';
import { date, money, number } from '../../utils/format.js';
import { formData, showErrors } from '../../utils/forms.js';
import { toast, toastError } from '../../components/toast.js';
import { checkbox, dateOnly, input, intInput, moneyInput, pageHead, select, textarea } from '../ui.js';

const CKINDS = [['percent', 'Porcentaje'], ['fixed', 'Monto fijo'], ['free_shipping', 'Envío gratis'], ['free_product', 'Producto gratis']];
const PKINDS = [['percent', 'Porcentaje'], ['fixed', 'Monto fijo por unidad (centavos)']];
const TARGETS = [['all', 'Toda la tienda'], ['category', 'Una categoría (ID)'], ['product', 'Un producto (ID)']];

const period = (x) => (x.starts_at || x.ends_at ? `${x.starts_at ? date(x.starts_at) : 'Ya'} a ${x.ends_at ? date(x.ends_at) : 'sin fin'}` : 'Siempre');

export default async function promotions(el) {
  let coupons = (await api.get('/admin/coupons')).items;
  let promos = (await api.get('/admin/promotions')).items;
  const draw = (editC = null, editP = null) => {
    render(el, html`
      ${pageHead('Cupones y promociones')}
      <section class="a-card">
        <div class="a-card__head"><h2 class="a-card__title">Cupones</h2>${editC === null ? html`<button class="btn btn--secondary" type="button" data-new-c>Nuevo cupón</button>` : ''}</div>
        <p class="help">Códigos que el cliente escribe en el carrito. Los cupones generados por recompensas se gestionan solos.</p>
        ${editC !== null ? html`<form class="a-subform" data-coupon novalidate>
          <p class="form-summary notice notice--error" role="alert" tabindex="-1" hidden></p>
          <div class="grid-2">${input('code', 'Código', editC.code, { required: true, attrs: 'maxlength="40"' })}${select('kind', 'Tipo', CKINDS, editC.kind || 'percent')}</div>
          ${input('description', 'Descripción', editC.description, { optional: true })}
          <div class="grid-2">${intInput('percent', 'Porcentaje', editC.percent, { optional: true, min: 0 })}${moneyInput('value_cents', 'Monto (Q)', editC.value_cents, { optional: true })}</div>
          <div class="grid-2">${moneyInput('min_subtotal_cents', 'Compra mínima (Q)', editC.min_subtotal_cents, { optional: true })}${intInput('product_id', 'ID de producto (producto gratis)', editC.product_id, { optional: true })}</div>
          <div class="grid-2">${intInput('max_uses', 'Usos totales', editC.max_uses, { optional: true, min: 1, help: 'Vacío = ilimitado.' })}${intInput('per_user_limit', 'Usos por cliente', editC.per_user_limit ?? 1, { min: 0, help: '0 = ilimitado.' })}</div>
          <div class="grid-2">${input('starts_at', 'Inicio', dateOnly(editC.starts_at), { type: 'date', optional: true })}${input('ends_at', 'Fin', dateOnly(editC.ends_at), { type: 'date', optional: true })}</div>
          ${checkbox('is_active', 'Activo', editC.is_active ?? true)}
          <div class="form-actions"><button class="btn btn--primary" type="submit">Guardar cupón</button><button class="btn btn--ghost" type="button" data-cancel>Cancelar</button></div>
        </form>` : ''}
        <div class="table-wrap"><table class="a-table"><thead><tr><th>Código</th><th>Beneficio</th><th>Vigencia</th><th class="num">Usos</th><th>Activo</th><th></th></tr></thead>
          <tbody>${coupons.map((c) => html`<tr data-cid="${c.id}"><td><span class="coupon-code">${c.code}</span></td>
            <td>${c.kind === 'percent' ? `${c.percent}%` : c.kind === 'fixed' ? money(c.value_cents) : c.kind === 'free_shipping' ? 'Envío gratis' : 'Producto gratis'}${c.min_subtotal_cents ? html`<br><small class="muted">Desde ${money(c.min_subtotal_cents)}</small>` : ''}</td>
            <td>${period(c)}</td><td class="num">${number(c.uses_count)}${c.max_uses ? ` / ${number(c.max_uses)}` : ''}</td><td>${c.is_active ? 'Sí' : 'No'}</td>
            <td class="a-actions"><button type="button" class="linklike" data-edit-c>Editar</button> <button type="button" class="linklike danger" data-del-c>Eliminar</button></td></tr>`)}</tbody></table></div>
      </section>
      <section class="a-card">
        <div class="a-card__head"><h2 class="a-card__title">Promociones automáticas</h2>${editP === null ? html`<button class="btn btn--secondary" type="button" data-new-p>Nueva promoción</button>` : ''}</div>
        <p class="help">Descuentos que se aplican solos al precio. Si varias coinciden, se usa la mejor para el cliente (no se acumulan).</p>
        ${editP !== null ? html`<form class="a-subform" data-promo novalidate>
          <p class="form-summary notice notice--error" role="alert" tabindex="-1" hidden></p>
          ${input('name', 'Nombre', editP.name, { required: true })}
          ${textarea('description', 'Descripción', editP.description, 2)}
          <div class="grid-2">${select('kind', 'Tipo', PKINDS, editP.kind || 'percent')}${intInput('value', 'Valor', editP.value, { min: 1, help: '% o centavos según el tipo.' })}</div>
          <div class="grid-2">${select('target', 'Se aplica a', TARGETS, editP.target || 'all')}${intInput('target_id', 'ID de categoría o producto', editP.target_id, { optional: true })}</div>
          <div class="grid-2">${input('starts_at', 'Inicio', dateOnly(editP.starts_at), { type: 'date', optional: true })}${input('ends_at', 'Fin', dateOnly(editP.ends_at), { type: 'date', optional: true })}</div>
          ${checkbox('is_active', 'Activa', editP.is_active ?? true)}
          <div class="form-actions"><button class="btn btn--primary" type="submit">Guardar promoción</button><button class="btn btn--ghost" type="button" data-cancel>Cancelar</button></div>
        </form>` : ''}
        <div class="table-wrap"><table class="a-table"><thead><tr><th>Promoción</th><th>Descuento</th><th>Aplica a</th><th>Vigencia</th><th>Activa</th><th></th></tr></thead>
          <tbody>${promos.map((p) => html`<tr data-pid="${p.id}"><td>${p.name}</td><td>${p.kind === 'percent' ? `${p.value}%` : money(p.value)}</td>
            <td>${p.target === 'all' ? 'Toda la tienda' : `${p.target === 'category' ? 'Categoría' : 'Producto'} ${p.target_id}`}</td><td>${period(p)}</td><td>${p.is_active ? 'Sí' : 'No'}</td>
            <td class="a-actions"><button type="button" class="linklike" data-edit-p>Editar</button> <button type="button" class="linklike danger" data-del-p>Eliminar</button></td></tr>`)}</tbody></table></div>
      </section>`);
    $('[data-new-c]', el)?.addEventListener('click', () => draw({}, null));
    $('[data-new-p]', el)?.addEventListener('click', () => draw(null, {}));
    $$('[data-cancel]', el).forEach((b) => b.addEventListener('click', () => draw()));
    $$('[data-edit-c]', el).forEach((b) => b.addEventListener('click', () => draw(coupons.find((c) => c.id === +b.closest('[data-cid]').dataset.cid))));
    $$('[data-edit-p]', el).forEach((b) => b.addEventListener('click', () => draw(null, promos.find((p) => p.id === +b.closest('[data-pid]').dataset.pid))));
    const del = async (url) => {
      if (!confirm('¿Eliminar? Si ya se usó, se desactivará para conservar el historial.')) return;
      try { await api.del(url); coupons = (await api.get('/admin/coupons')).items; promos = (await api.get('/admin/promotions')).items; toast('Listo.'); draw(); } catch (err) { toastError(err); }
    };
    $$('[data-del-c]', el).forEach((b) => b.addEventListener('click', () => del(`/admin/coupons/${b.closest('[data-cid]').dataset.cid}`)));
    $$('[data-del-p]', el).forEach((b) => b.addEventListener('click', () => del(`/admin/promotions/${b.closest('[data-pid]').dataset.pid}`)));
    const fc = $('[data-coupon]', el);
    fc?.addEventListener('submit', async (e) => {
      e.preventDefault();
      try { if (editC.id) await api.put(`/admin/coupons/${editC.id}`, formData(fc)); else await api.post('/admin/coupons', formData(fc)); coupons = (await api.get('/admin/coupons')).items; toast('Cupón guardado.'); draw(); } catch (err) { showErrors(fc, err); }
    });
    const fp = $('[data-promo]', el);
    fp?.addEventListener('submit', async (e) => {
      e.preventDefault();
      try { if (editP.id) await api.put(`/admin/promotions/${editP.id}`, formData(fp)); else await api.post('/admin/promotions', formData(fp)); promos = (await api.get('/admin/promotions')).items; toast('Promoción guardada.'); draw(); } catch (err) { showErrors(fp, err); }
    });
  };
  draw();
}
