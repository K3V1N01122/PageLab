import { html, render, $, $$ } from '../utils/html.js';
import { api } from '../services/api.js';
import { cart } from '../services/cart.js';
import { toggleFavorite } from '../services/auth.js';
import { store } from '../store/store.js';
import { navigate, setTitle } from '../router.js';
import { breadcrumb } from '../components/breadcrumb.js';
import { availability, demoBadge, price } from '../components/price.js';
import { productGrid } from '../components/productCard.js';
import { icons } from '../components/icons.js';
import { toast, toastError } from '../components/toast.js';
import { loading } from '../components/states.js';
import { money, number } from '../utils/format.js';

export default async function product(el, ctx) {
  render(el, html`<div class="container">${loading('Cargando producto…')}</div>`);
  let p;
  try {
    p = await api.get(`/products/${encodeURIComponent(ctx.params.slug)}`);
  } catch (err) {
    if (err.status === 404) { const m = await import('./notFound.js'); return m.default(el); }
    throw err;
  }
  setTitle(p.seo_title || p.name);
  const { config, favorites } = store.get();
  const fav = favorites.has(p.id);
  const out = p.availability === 'out_of_stock';
  const maxQty = Math.min(p.stock, 99);
  const earn = config.loyalty.enabled ? Math.floor(p.price_cents / 100) * config.loyalty.points_per_currency_unit : 0;
  const images = p.images.length ? p.images : [];
  const crumbs = [{ name: 'Catálogo', href: '/catalogo' },
    ...p.breadcrumb.map((b) => ({ name: b.name, href: `/categoria/${b.slug}` })), { name: p.name }];

  render(el, html`
    <div class="container product-page">
      ${breadcrumb(crumbs)}
      <div class="product">
        <div class="gallery">
          <div class="gallery__main">
            ${images.length ? html`<img src="${images[0].url}" alt="${images[0].alt || p.name}" width="900" height="900" data-main>`
              : html`<div class="gallery__empty">Sin imagen</div>`}
          </div>
          ${images.length > 1 ? html`<ul class="gallery__thumbs" aria-label="Imágenes del producto">
            ${images.map((img, i) => html`<li><button type="button" class="gallery__thumb ${i === 0 ? 'is-active' : ''}" data-index="${i}"
              aria-label="Ver imagen ${i + 1} de ${images.length}" aria-pressed="${i === 0}">
              <img src="${img.url}" alt="" loading="lazy" width="120" height="120"></button></li>`)}
          </ul>` : ''}
        </div>
        <div class="product__info">
          ${p.category ? html`<a class="product__cat" href="/categoria/${p.category.slug}" data-link>${p.category.name}</a>` : ''}
          <h1 class="product__title">${p.name}</h1>
          ${demoBadge(p)}
          ${price(p, 'lg')}
          ${p.promotion ? html`<p class="product__promo">${p.promotion}</p>` : ''}
          ${p.short_description ? html`<p class="product__short">${p.short_description}</p>` : ''}
          <dl class="product__facts">
            <div><dt>Disponibilidad</dt><dd>${availability(p, true)}</dd></div>
            <div><dt>SKU</dt><dd>${p.sku}</dd></div>
            ${earn ? html`<div><dt>Puntos</dt><dd class="text-brass">Sumas ${number(earn)} puntos por unidad</dd></div>` : ''}
          </dl>
          <form class="buy" data-buy>
            <div class="qty">
              <label for="qty" class="qty__label">Cantidad</label>
              <div class="qty__control">
                <button type="button" class="icon-btn" data-step="-1" aria-label="Disminuir cantidad" ${out ? 'disabled' : ''}>${icons.minus}</button>
                <input id="qty" name="qty" type="number" inputmode="numeric" min="1" max="${maxQty || 1}" value="1" ${out ? 'disabled' : ''}>
                <button type="button" class="icon-btn" data-step="1" aria-label="Aumentar cantidad" ${out ? 'disabled' : ''}>${icons.plus}</button>
              </div>
            </div>
            <div class="buy__actions">
              <button type="submit" class="btn btn--primary btn--lg" name="action" value="add" ${out ? 'disabled' : ''}>${out ? 'Agotado' : 'Agregar al carrito'}</button>
              <button type="button" class="btn btn--secondary btn--lg" data-buy-now ${out ? 'disabled' : ''}>Comprar ahora</button>
              <button type="button" class="icon-btn icon-btn--outline ${fav ? 'is-active' : ''}" data-fav aria-pressed="${fav}"
                aria-label="${fav ? 'Quitar de favoritos' : 'Agregar a favoritos'}">${fav ? icons.heartFill : icons.heart}</button>
            </div>
          </form>
          ${config.free_shipping_over_cents ? html`<p class="muted">Envío gratis en compras desde ${money(config.free_shipping_over_cents)}.</p>` : ''}
        </div>
      </div>
      <div class="product__details">
        <section aria-labelledby="h-desc">
          <h2 id="h-desc" class="section__title">Descripción</h2>
          <div class="prose">${(p.description || 'Sin descripción.').split(/\n{2,}/).map((para) => html`<p>${para}</p>`)}</div>
        </section>
        ${Object.keys(p.attributes).length ? html`
        <section aria-labelledby="h-attrs">
          <h2 id="h-attrs" class="section__title">Información adicional</h2>
          <table class="attrs"><tbody>${Object.entries(p.attributes).map(([k, v]) => html`<tr><th scope="row">${k}</th><td>${v}</td></tr>`)}</tbody></table>
          ${p.tags.length ? html`<ul class="tags" aria-label="Etiquetas">${p.tags.map((t) => html`<li>${t.name}</li>`)}</ul>` : ''}
        </section>` : ''}
      </div>
      ${p.related.length ? html`
      <section class="section" aria-labelledby="h-related">
        <h2 id="h-related" class="section__title">También te puede interesar</h2>
        ${productGrid(p.related)}
      </section>` : ''}
    </div>`);

  const qty = $('#qty', el);
  const clamp = () => { qty.value = Math.max(1, Math.min(maxQty || 1, parseInt(qty.value, 10) || 1)); };
  $$('[data-step]', el).forEach((b) => b.addEventListener('click', () => { qty.value = (parseInt(qty.value, 10) || 1) + parseInt(b.dataset.step, 10); clamp(); }));
  qty?.addEventListener('change', clamp);
  $$('.gallery__thumb', el).forEach((b) => b.addEventListener('click', () => {
    const img = images[parseInt(b.dataset.index, 10)];
    const main = $('[data-main]', el);
    main.src = img.url;
    main.alt = img.alt || p.name;
    $$('.gallery__thumb', el).forEach((t) => { t.classList.toggle('is-active', t === b); t.setAttribute('aria-pressed', String(t === b)); });
  }));
  const add = async () => { clamp(); await cart.add(p.id, parseInt(qty.value, 10)); };
  $('[data-buy]', el).addEventListener('submit', async (e) => {
    e.preventDefault();
    const btn = e.submitter || $('[type="submit"]', el);
    btn.disabled = true;
    try { await add(); toast('Producto agregado al carrito.'); } catch (err) { toastError(err); } finally { btn.disabled = false; }
  });
  $('[data-buy-now]', el).addEventListener('click', async (e) => {
    e.target.disabled = true;
    try { await add(); navigate(store.get().user ? '/checkout' : '/carrito'); } catch (err) { toastError(err); e.target.disabled = false; }
  });
  $('[data-fav]', el).addEventListener('click', async (e) => {
    const b = e.currentTarget;
    if (!store.get().user) { navigate(`/iniciar-sesion?next=${encodeURIComponent(location.pathname)}`); return; }
    try {
      const on = await toggleFavorite(p.id);
      b.classList.toggle('is-active', on);
      b.setAttribute('aria-pressed', String(on));
      b.setAttribute('aria-label', on ? 'Quitar de favoritos' : 'Agregar a favoritos');
      b.innerHTML = String(on ? icons.heartFill : icons.heart);
      toast(on ? 'Guardado en favoritos.' : 'Quitado de favoritos.');
    } catch (err) { toastError(err); }
  });
}
