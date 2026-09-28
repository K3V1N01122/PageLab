import { html, render, $, $$ } from '../../utils/html.js';
import { api } from '../../services/api.js';
import { formData, showErrors } from '../../utils/forms.js';
import { toast, toastError } from '../../components/toast.js';
import { can } from '../main.js';
import { checkbox, input, intInput, pageHead, select, textarea, yesNo } from '../ui.js';

export default async function categories(el) {
  let items = (await api.get('/admin/categories')).items;
  const byId = () => Object.fromEntries(items.map((c) => [c.id, c]));
  const draw = (editing = null) => {
    const map = byId();
    render(el, html`
      ${pageHead('Categorías', can('products.write') && editing === null ? html`<button class="btn btn--primary" type="button" data-new>Nueva categoría</button>` : '')}
      ${editing !== null ? html`
      <form class="a-card a-form-narrow" data-cat novalidate>
        <h2 class="a-card__title">${editing.id ? 'Editar categoría' : 'Nueva categoría'}</h2>
        <p class="form-summary notice notice--error" role="alert" tabindex="-1" hidden></p>
        ${input('name', 'Nombre', editing.name, { required: true })}
        ${input('slug', 'URL amigable', editing.slug, { optional: true })}
        ${select('parent_id', 'Categoría superior', items.filter((c) => c.id !== editing.id).map((c) => [c.id, c.name]), editing.parent_id, { optional: true, empty: 'Ninguna (categoría principal)' })}
        ${textarea('description', 'Descripción', editing.description, 3)}
        ${intInput('sort_order', 'Orden', editing.sort_order ?? 0)}
        ${checkbox('is_active', 'Visible en la tienda', editing.is_active ?? true)}
        ${input('seo_title', 'Título SEO', editing.seo_title, { optional: true, attrs: 'maxlength="70"' })}
        ${input('seo_description', 'Descripción SEO', editing.seo_description, { optional: true, attrs: 'maxlength="170"' })}
        <div class="form-actions"><button class="btn btn--primary" type="submit">Guardar</button><button class="btn btn--ghost" type="button" data-cancel>Cancelar</button></div>
      </form>` : ''}
      <div class="table-wrap"><table class="a-table">
        <thead><tr><th>Nombre</th><th>Superior</th><th class="num">Productos</th><th>Visible</th><th class="num">Orden</th><th></th></tr></thead>
        <tbody>${items.map((c) => html`<tr data-id="${c.id}"><td>${c.name}<br><small class="muted">/categoria/${c.slug}</small></td>
          <td>${c.parent_id ? map[c.parent_id]?.name : '—'}</td><td class="num">${c.product_count}</td><td>${yesNo(c.is_active)}</td><td class="num">${c.sort_order}</td>
          <td class="a-actions">${can('products.write') ? html`<button type="button" class="linklike" data-edit>Editar</button> <button type="button" class="linklike danger" data-del>Eliminar</button>` : ''}</td></tr>`)}</tbody>
      </table></div>`);
    $('[data-new]', el)?.addEventListener('click', () => draw({}));
    $('[data-cancel]', el)?.addEventListener('click', () => draw());
    $$('[data-edit]', el).forEach((b) => b.addEventListener('click', () => draw(byId()[b.closest('[data-id]').dataset.id])));
    $$('[data-del]', el).forEach((b) => b.addEventListener('click', async () => {
      if (!confirm('¿Eliminar esta categoría?')) return;
      try { await api.del(`/admin/categories/${b.closest('[data-id]').dataset.id}`); items = (await api.get('/admin/categories')).items; toast('Categoría eliminada.'); draw(); } catch (err) { toastError(err); }
    }));
    const f = $('[data-cat]', el);
    f?.addEventListener('submit', async (e) => {
      e.preventDefault();
      try {
        if (editing.id) await api.put(`/admin/categories/${editing.id}`, formData(f)); else await api.post('/admin/categories', formData(f));
        items = (await api.get('/admin/categories')).items;
        toast('Categoría guardada.');
        draw();
      } catch (err) { showErrors(f, err); }
    });
  };
  draw();
}
