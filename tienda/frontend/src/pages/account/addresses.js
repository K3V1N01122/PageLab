import { html, render, $, $$ } from '../../utils/html.js';
import { api } from '../../services/api.js';
import { setTitle } from '../../router.js';
import { formData, showErrors, submitting } from '../../utils/forms.js';
import { toast, toastError } from '../../components/toast.js';
import { accountLayout, bindLayout } from './layout.js';

const form = (a = {}) => html`
  <form class="form-card" data-address="${a.id || ''}" novalidate>
    <h2 class="section__title">${a.id ? 'Editar dirección' : 'Nueva dirección'}</h2>
    <p class="form-summary notice notice--error" role="alert" tabindex="-1" hidden></p>
    <div class="grid-2">
      <div class="field"><label for="label">Nombre de la dirección <span class="optional">(opcional)</span></label><input id="label" name="label" value="${a.label || ''}" placeholder="Casa, oficina…" maxlength="50"></div>
      <div class="field"><label for="recipient">Quién recibe</label><input id="recipient" name="recipient" value="${a.recipient || ''}" required maxlength="120"></div>
    </div>
    <div class="field"><label for="phone">Teléfono</label><input id="phone" name="phone" type="tel" value="${a.phone || ''}" required maxlength="30"></div>
    <div class="field"><label for="line1">Dirección</label><input id="line1" name="line1" value="${a.line1 || ''}" required maxlength="200"></div>
    <div class="field"><label for="line2">Referencia <span class="optional">(opcional)</span></label><input id="line2" name="line2" value="${a.line2 || ''}" maxlength="200"></div>
    <div class="grid-2">
      <div class="field"><label for="city">Municipio o ciudad</label><input id="city" name="city" value="${a.city || ''}" required maxlength="100"></div>
      <div class="field"><label for="state">Departamento <span class="optional">(opcional)</span></label><input id="state" name="state" value="${a.state || ''}" maxlength="100"></div>
    </div>
    <label class="check"><input type="checkbox" name="is_default" ${a.is_default ? 'checked' : ''}> Usar como dirección principal</label>
    <div class="form-actions"><button class="btn btn--primary" type="submit">Guardar dirección</button>
      <button class="btn btn--ghost" type="button" data-cancel>Cancelar</button></div>
  </form>`;

export default async function addresses(el) {
  setTitle('Direcciones');
  let items = (await api.get('/account/profile')).addresses;
  const draw = (editing = null) => {
    render(el, accountLayout('/cuenta/direcciones', 'Direcciones', html`
      ${items.length ? html`<ul class="address-list">${items.map((a) => html`
        <li class="address" data-id="${a.id}">
          <p><strong>${a.label || a.recipient}</strong> ${a.is_default ? html`<span class="pill">Principal</span>` : ''}</p>
          <p>${a.recipient}, ${a.phone}</p><p>${a.line1}${a.line2 ? `, ${a.line2}` : ''}</p><p>${a.city}${a.state ? `, ${a.state}` : ''}</p>
          <div class="form-actions"><button type="button" class="btn btn--ghost" data-edit>Editar</button><button type="button" class="btn btn--ghost" data-del>Eliminar</button></div>
        </li>`)}</ul>` : html`<p class="muted">Aún no tienes direcciones guardadas.</p>`}
      ${editing !== null ? form(editing) : html`<button type="button" class="btn btn--secondary" data-new>Agregar dirección</button>`}`));
    bindLayout(el);
    $('[data-new]', el)?.addEventListener('click', () => draw({}));
    $$('[data-edit]', el).forEach((b) => b.addEventListener('click', () => draw(items.find((a) => a.id === +b.closest('[data-id]').dataset.id))));
    $$('[data-del]', el).forEach((b) => b.addEventListener('click', async () => {
      if (!confirm('¿Eliminar esta dirección?')) return;
      try { items = (await api.del(`/account/addresses/${b.closest('[data-id]').dataset.id}`)).items; toast('Dirección eliminada.'); draw(); } catch (err) { toastError(err); }
    }));
    const f = $('[data-address]', el);
    $('[data-cancel]', el)?.addEventListener('click', () => draw());
    f?.addEventListener('submit', (e) => {
      e.preventDefault();
      submitting(f, async () => {
        try {
          const id = f.dataset.address;
          items = (id ? await api.put(`/account/addresses/${id}`, formData(f)) : await api.post('/account/addresses', formData(f))).items;
          toast('Dirección guardada.');
          draw();
        } catch (err) { showErrors(f, err); }
      });
    });
  };
  draw();
}
