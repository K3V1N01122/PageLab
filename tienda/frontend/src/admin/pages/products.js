import { html, render, $, $$ } from '../../utils/html.js';
import { api } from '../../services/api.js';
import { money, number } from '../../utils/format.js';
import { formData, showErrors, clearErrors } from '../../utils/forms.js';
import { pagination } from '../../components/pagination.js';
import { toast, toastError } from '../../components/toast.js';
import { go, can } from '../main.js';
import { checkbox, input, intInput, moneyInput, pageHead, select, textarea } from '../ui.js';

const STATUS = [['active', 'Publicado'], ['draft', 'Borrador'], ['archived', 'Archivado']];
const statusLabel = Object.fromEntries(STATUS);

export default async function products(el, ctx) {
  if (ctx.sub[0] === 'nuevo') return form(el, null);
  if (ctx.sub[0]) return form(el, parseInt(ctx.sub[0], 10));
  const q = ctx.query;
  const page = parseInt(q.get('page') || '1', 10) || 1;
  const [data, { items: cats }] = await Promise.all([
    api.get('/admin/products', { page, q: q.get('q'), status: q.get('status'), category_id: q.get('category_id'), low_stock: q.get('low_stock') }),
    api.get('/admin/categories')]);
  render(el, html`
    ${pageHead('Productos', can('products.write') ? html`<a class="btn btn--primary" href="/admin/productos/nuevo">Nuevo producto</a>` : '')}
    <form class="a-filters" data-filters role="search">
      <div class="field"><label for="q">Buscar</label><input id="q" name="q" type="search" value="${q.get('q') || ''}" placeholder="Nombre, SKU o etiqueta"></div>
      <div class="field"><label for="st">Estado</label><select id="st" name="status"><option value="">Todos</option>${STATUS.map(([v, l]) => html`<option value="${v}" ${v === q.get('status') ? 'selected' : ''}>${l}</option>`)}</select></div>
      <div class="field"><label for="cat">Categoría</label><select id="cat" name="category_id"><option value="">Todas</option>${cats.map((c) => html`<option value="${c.id}" ${String(c.id) === q.get('category_id') ? 'selected' : ''}>${c.name}</option>`)}</select></div>
      <label class="check"><input type="checkbox" name="low_stock" value="1" ${q.get('low_stock') ? 'checked' : ''}> Poco stock</label>
      <button class="btn btn--primary" type="submit">Filtrar</button>
    </form>
    <p class="muted">${number(data.pagination.total)} productos</p>
    <div class="table-wrap"><table class="a-table">
      <thead><tr><th></th><th>Producto</th><th>SKU</th><th>Categoría</th><th>Estado</th><th class="num">Precio</th><th class="num">Stock</th><th class="num">Vendidos</th></tr></thead>
      <tbody>${data.items.map((p) => html`<tr>
        <td>${p.image_url ? html`<img class="a-thumb" src="${p.image_url}" alt="" width="44" height="44" loading="lazy">` : ''}</td>
        <td><a href="/admin/productos/${p.id}">${p.name}</a> ${p.is_demo ? html`<span class="demo-badge">Prueba</span>` : ''} ${p.is_featured ? html`<span class="pill">Destacado</span>` : ''}<br><small class="muted">ID ${p.id}</small></td>
        <td>${p.sku}</td><td>${p.category_name || '—'}</td><td><span class="pill pill--${p.status === 'active' ? 'delivered' : p.status === 'draft' ? 'pending' : 'cancelled'}">${statusLabel[p.status]}</span></td>
        <td class="num">${money(p.price_cents)}</td><td class="num ${p.stock <= p.low_stock_threshold ? 'neg' : ''}">${p.stock}</td><td class="num">${p.sold_count}</td></tr>`)}</tbody>
    </table></div>
    ${pagination(data.pagination, (n) => { const p = new URLSearchParams(location.search); p.set('page', n); return `/admin/productos?${p}`; })}`);
  $('[data-filters]', el).addEventListener('submit', (e) => {
    e.preventDefault();
    go(`/admin/productos?${new URLSearchParams([...new FormData(e.target)].filter(([, v]) => v))}`);
  });
}

const attrsToText = (a) => Object.entries(a || {}).map(([k, v]) => `${k}: ${v}`).join('\n');
const textToAttrs = (t) => Object.fromEntries((t || '').split('\n').map((l) => l.split(':')).filter((p) => p.length >= 2 && p[0].trim())
  .map(([k, ...v]) => [k.trim(), v.join(':').trim()]));

async function form(el, id) {
  const [p, { items: cats }] = await Promise.all([
    id ? api.get(`/admin/products/${id}`) : Promise.resolve({ status: 'draft', images: [], tags: [], related_ids: [], attributes: {}, stock: 0, low_stock_threshold: 5 }),
    api.get('/admin/categories')]);
  let images = [...p.images];
  const writable = can('products.write');
  const stockEditable = can('inventory.write');
  const draw = () => {
    render(el, html`
      ${pageHead(id ? p.name : 'Nuevo producto', html`<a class="btn btn--ghost" href="/admin/productos">Volver</a>
        ${id && p.status === 'active' ? html`<a class="btn btn--ghost" href="/producto/${p.slug}" target="_blank" rel="noopener">Ver en la tienda</a>` : ''}`)}
      ${p.is_demo ? html`<div class="notice notice--warn"><p>Este es un producto de demostración. Edítalo con datos reales o elimínalo antes de publicar la tienda.</p></div>` : ''}
      <form class="a-form" data-product novalidate>
        <p class="form-summary notice notice--error" role="alert" tabindex="-1" hidden></p>
        <div class="a-grid a-grid--form">
          <div>
            <section class="a-card"><h2 class="a-card__title">Información</h2>
              ${input('name', 'Nombre', p.name, { required: true, attrs: 'maxlength="200"' })}
              <div class="grid-2">${input('sku', 'SKU', p.sku, { required: true, attrs: 'maxlength="64"' })}${input('slug', 'URL amigable', p.slug, { optional: true, help: 'Se genera a partir del nombre si lo dejas vacío.' })}</div>
              ${input('short_description', 'Descripción corta', p.short_description, { optional: true, attrs: 'maxlength="300"' })}
              ${textarea('description', 'Descripción', p.description, 6)}
              ${textarea('attributes_text', 'Información adicional', attrsToText(p.attributes), 4)}
              <p class="help">Una línea por dato, con el formato <em>Nombre: valor</em> (p. ej. Material: algodón).</p>
            </section>
            <section class="a-card"><h2 class="a-card__title">Imágenes</h2>
              <ul class="a-images">${images.map((img, i) => html`<li>
                <img src="${img.url}" alt="" width="120" height="120">
                <label class="sr-only" for="alt-${i}">Texto alternativo de la imagen ${i + 1}</label>
                <input id="alt-${i}" data-alt="${i}" value="${img.alt || ''}" placeholder="Texto alternativo" maxlength="200">
                <div class="a-images__actions">
                  <button type="button" class="linklike" data-move="${i}" ${i === 0 ? 'disabled' : ''}>Hacer principal</button>
                  <button type="button" class="linklike danger" data-remove-img="${i}">Quitar</button></div></li>`)}</ul>
              ${writable ? html`<label class="btn btn--secondary a-upload">Subir imagen<input type="file" accept="image/jpeg,image/png,image/webp,image/gif" data-upload class="sr-only"></label>
                <p class="help">JPG, PNG, WebP o GIF, hasta 8 MB. Se optimizan automáticamente.</p>` : ''}
            </section>
            <section class="a-card"><h2 class="a-card__title">SEO</h2>
              ${input('seo_title', 'Título para buscadores', p.seo_title, { optional: true, attrs: 'maxlength="70"', help: 'Máximo 70 caracteres. Si lo dejas vacío se usa el nombre.' })}
              ${input('seo_description', 'Descripción para buscadores', p.seo_description, { optional: true, attrs: 'maxlength="170"' })}
            </section>
          </div>
          <div>
            <section class="a-card"><h2 class="a-card__title">Publicación</h2>
              ${select('status', 'Estado', STATUS, p.status)}
              ${checkbox('is_featured', 'Mostrar en destacados', p.is_featured)}
              ${select('category_id', 'Categoría', cats.map((c) => [c.id, c.name]), p.category_id, { optional: true, empty: 'Sin categoría' })}
              ${input('tags', 'Etiquetas', (p.tags || []).join(', '), { optional: true, help: 'Separadas por comas.' })}
              ${input('related', 'Productos relacionados (IDs)', (p.related_ids || []).join(', '), { optional: true, help: 'IDs separados por comas. Si lo dejas vacío se sugieren de la misma categoría.' })}
            </section>
            <section class="a-card"><h2 class="a-card__title">Precio e inventario</h2>
              ${moneyInput('price_cents', 'Precio (Q)', p.price_cents, { required: true })}
              ${moneyInput('compare_at_cents', 'Precio anterior (Q)', p.compare_at_cents, { optional: true, help: 'Se muestra tachado si es mayor al precio.' })}
              ${stockEditable ? intInput('stock', 'Stock', p.stock, { min: 0 }) : html`<p>Stock: <strong>${p.stock}</strong> <span class="muted">(tu rol no puede modificarlo)</span></p>`}
              ${intInput('low_stock_threshold', 'Aviso de poco stock', p.low_stock_threshold, { min: 0 })}
            </section>
            ${writable ? html`<div class="a-form__actions">
              <button class="btn btn--primary btn--block btn--lg" type="submit">${id ? 'Guardar cambios' : 'Crear producto'}</button>
              ${id ? html`<button class="btn btn--ghost btn--block danger" type="button" data-delete>Eliminar producto</button>` : ''}
            </div>` : ''}
          </div>
        </div>
      </form>`);
    bind();
  };
  const syncAlts = () => $$('[data-alt]', el).forEach((i) => { images[+i.dataset.alt].alt = i.value; });
  const bind = () => {
    const f = $('[data-product]', el);
    $('[data-upload]', el)?.addEventListener('change', async (e) => {
      const file = e.target.files[0];
      if (!file) return;
      syncAlts();
      try { const r = await api.upload('/admin/uploads', file); images.push({ url: r.url, alt: f.name.value }); keep(f); draw(); toast('Imagen subida. Guarda para confirmar.'); }
      catch (err) { toastError(err); }
    });
    $$('[data-remove-img]', el).forEach((b) => b.addEventListener('click', () => { syncAlts(); keep(f); images.splice(+b.dataset.removeImg, 1); draw(); }));
    $$('[data-move]', el).forEach((b) => b.addEventListener('click', () => { syncAlts(); keep(f); const [img] = images.splice(+b.dataset.move, 1); images.unshift(img); draw(); }));
    f.addEventListener('submit', async (e) => {
      e.preventDefault();
      clearErrors(f);
      syncAlts();
      const d = formData(f);
      const body = {
        ...d, images,
        tags: (d.tags || '').split(',').map((t) => t.trim()).filter(Boolean),
        related_ids: (d.related || '').split(',').map((t) => parseInt(t, 10)).filter(Boolean),
        attributes: textToAttrs(d.attributes_text),
      };
      delete body.attributes_text; delete body.related;
      if (!stockEditable) delete body.stock;
      const btn = f.querySelector('[type=submit]');
      btn.disabled = true;
      try {
        const saved = id ? await api.put(`/admin/products/${id}`, body) : await api.post('/admin/products', body);
        toast(id ? 'Cambios guardados.' : 'Producto creado.');
        go(`/admin/productos/${saved.id}`, true);
      } catch (err) { showErrors(f, err); btn.disabled = false; }
    });
    $('[data-delete]', el)?.addEventListener('click', async () => {
      if (!confirm('¿Eliminar este producto? Si tiene ventas, se archivará para conservar el historial.')) return;
      try { const r = await api.del(`/admin/products/${id}`); toast(r.result === 'archived' ? 'El producto tenía ventas: se archivó.' : 'Producto eliminado.'); go('/admin/productos'); }
      catch (err) { toastError(err); }
    });
  };
  // Conserva lo escrito al redibujar tras subir/quitar imágenes.
  const keep = (f) => {
    const d = formData(f);
    Object.assign(p, {
      name: d.name, sku: d.sku, slug: d.slug, short_description: d.short_description, description: d.description,
      attributes: textToAttrs(d.attributes_text), seo_title: d.seo_title, seo_description: d.seo_description, status: d.status,
      is_featured: d.is_featured, category_id: d.category_id, tags: (d.tags || '').split(',').map((t) => t.trim()).filter(Boolean),
      related_ids: (d.related || '').split(',').map((t) => parseInt(t, 10)).filter(Boolean), price_cents: d.price_cents,
      compare_at_cents: d.compare_at_cents, stock: d.stock ?? p.stock, low_stock_threshold: d.low_stock_threshold,
    });
  };
  draw();
}
