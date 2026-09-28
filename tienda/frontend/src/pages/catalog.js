import { html, render, $ } from '../utils/html.js';
import { api } from '../services/api.js';
import { navigate, setTitle } from '../router.js';
import { productGrid } from '../components/productCard.js';
import { pagination } from '../components/pagination.js';
import { breadcrumb } from '../components/breadcrumb.js';
import { empty, errorState, skeletonGrid } from '../components/states.js';
import { plural } from '../utils/format.js';

const SORTS = [
  ['newest', 'Más recientes'], ['best_selling', 'Más vendidos'], ['price_asc', 'Precio: menor a mayor'],
  ['price_desc', 'Precio: mayor a menor'], ['name', 'Nombre (A-Z)'],
];

function flatten(tree, depth = 0) {
  return tree.flatMap((c) => [{ ...c, depth }, ...flatten(c.children || [], depth + 1)]);
}

export default async function catalog(el, ctx) {
  const q = ctx.query;
  const slug = ctx.params.slug;
  const isSearch = ctx.path.startsWith('/buscar');
  const isSale = ctx.path.startsWith('/ofertas');
  const page = parseInt(q.get('page') || '1', 10) || 1;
  const filters = {
    q: q.get('q') || '', category: slug || q.get('categoria') || '', sort: q.get('sort') || 'newest',
    in_stock: q.get('disponibles') === '1' ? 1 : '', min: q.get('min') || '', max: q.get('max') || '',
  };
  let category = null;
  const tree = await api.get('/categories').then((r) => r.items).catch(() => []);
  if (slug) {
    try { category = await api.get(`/categories/${encodeURIComponent(slug)}`); } catch (err) {
      if (err.status === 404) { const m = await import('./notFound.js'); return m.default(el); }
      throw err;
    }
  }
  const title = category ? category.name : isSearch ? (filters.q ? `Resultados para “${filters.q}”` : 'Buscar') : isSale ? 'Ofertas' : 'Catálogo';
  setTitle(title);
  const crumbs = category ? [{ name: 'Catálogo', href: '/catalogo' }, ...category.breadcrumb.map((b, i, arr) =>
    i === arr.length - 1 ? { name: b.name } : { name: b.name, href: `/categoria/${b.slug}` })] : [{ name: title }];

  render(el, html`
    <div class="container catalog">
      ${breadcrumb(crumbs)}
      <header class="page-head">
        <h1 class="page-title">${title}</h1>
        ${category?.description ? html`<p class="page-lead">${category.description}</p>` : ''}
        <p class="page-meta" data-slot="count" aria-live="polite"></p>
      </header>
      <div class="catalog__layout">
        <aside class="filters" aria-label="Filtros">
          <details class="filters__panel" open>
            <summary>Filtrar</summary>
            <form data-filters>
              ${isSearch ? html`<div class="field"><label for="f-q">Buscar</label><input id="f-q" name="q" type="search" value="${filters.q}" maxlength="100"></div>` : ''}
              ${!slug ? html`<div class="field"><label for="f-cat">Categoría</label>
                <select id="f-cat" name="categoria"><option value="">Todas</option>
                  ${flatten(tree).map((c) => html`<option value="${c.slug}" ${c.slug === filters.category ? 'selected' : ''}>${'— '.repeat(c.depth)}${c.name}</option>`)}
                </select></div>` : ''}
              <fieldset class="field field--range"><legend>Precio (Q)</legend>
                <label class="sr-only" for="f-min">Precio mínimo</label><input id="f-min" name="min" type="number" min="0" step="1" inputmode="numeric" placeholder="Mín." value="${filters.min}">
                <label class="sr-only" for="f-max">Precio máximo</label><input id="f-max" name="max" type="number" min="0" step="1" inputmode="numeric" placeholder="Máx." value="${filters.max}">
              </fieldset>
              <label class="check"><input type="checkbox" name="disponibles" value="1" ${filters.in_stock ? 'checked' : ''}> Solo disponibles</label>
              <div class="field"><label for="f-sort">Ordenar por</label>
                <select id="f-sort" name="sort">${SORTS.map(([v, l]) => html`<option value="${v}" ${v === filters.sort ? 'selected' : ''}>${l}</option>`)}</select></div>
              <button class="btn btn--primary btn--block" type="submit">Aplicar filtros</button>
              <a class="btn btn--ghost btn--block" href="${ctx.path}" data-link>Limpiar</a>
            </form>
          </details>
          ${slug && category && tree.length ? subcats(tree, category) : ''}
        </aside>
        <section class="catalog__results" data-slot="results" aria-label="Productos">${skeletonGrid(8)}</section>
      </div>
    </div>`);

  $('[data-filters]', el).addEventListener('submit', (e) => {
    e.preventDefault();
    const fd = new FormData(e.target);
    const params = new URLSearchParams();
    for (const [k, v] of fd.entries()) if (v !== '' && !(k === 'sort' && v === 'newest')) params.set(k, v);
    const base = params.get('categoria') && !slug ? `/categoria/${params.get('categoria')}` : ctx.path;
    params.delete('categoria');
    navigate(`${base}${params.toString() ? `?${params}` : ''}`);
  });

  const results = $('[data-slot="results"]', el);
  const load = async () => {
    try {
      const data = await api.get('/products', {
        page, page_size: 24, q: filters.q, category: filters.category, sort: filters.sort, in_stock: filters.in_stock,
        on_sale: isSale ? 1 : '', min_price: filters.min ? Math.round(filters.min * 100) : '', max_price: filters.max ? Math.round(filters.max * 100) : '',
      });
      $('[data-slot="count"]', el).textContent = plural(data.pagination.total, 'producto', 'productos');
      if (!data.items.length) {
        render(results, empty(isSearch ? 'No encontramos productos con esa búsqueda' : 'No hay productos aquí todavía',
          'Prueba con otras palabras o quita algunos filtros.', { href: '/catalogo', label: 'Ver todo el catálogo' }));
        return;
      }
      const hrefFor = (n) => { const p = new URLSearchParams(location.search); p.set('page', n); return `${ctx.path}?${p}`; };
      render(results, html`${productGrid(data.items)}${pagination(data.pagination, hrefFor)}`);
    } catch (err) {
      render(results, errorState(err));
      $('[data-action="retry"]', results)?.addEventListener('click', load);
    }
  };
  await load();
}

function subcats(tree, category) {
  const node = flatten(tree).find((c) => c.slug === category.slug);
  if (!node?.children?.length) return '';
  return html`<nav class="subcats" aria-label="Subcategorías"><h2 class="filters__title">Subcategorías</h2><ul>
    ${node.children.map((c) => html`<li><a href="/categoria/${c.slug}" data-link>${c.name} <small>(${c.total_count})</small></a></li>`)}</ul></nav>`;
}
