import { html } from '../utils/html.js';
import { store } from '../store/store.js';
import { icons } from './icons.js';
import { availability, demoBadge, price } from './price.js';

export function productCard(p) {
  const fav = store.get().favorites.has(p.id);
  const out = p.availability === 'out_of_stock';
  return html`
  <article class="product-card" data-product-id="${p.id}">
    <a class="product-card__media" href="/producto/${p.slug}" data-link tabindex="-1" aria-hidden="true">
      ${p.image
        ? html`<img src="${p.image.url}" alt="" loading="lazy" decoding="async" width="600" height="600">`
        : html`<span class="product-card__noimg">Sin imagen</span>`}
      ${p.compare_at_cents ? html`<span class="tag tag--sale">Oferta</span>` : ''}
    </a>
    <button type="button" class="icon-btn product-card__fav ${fav ? 'is-active' : ''}" data-action="favorite" data-id="${p.id}"
      aria-pressed="${fav}" aria-label="${fav ? 'Quitar de favoritos' : 'Agregar a favoritos'}: ${p.name}">
      ${fav ? icons.heartFill : icons.heart}
    </button>
    <div class="product-card__body">
      ${p.category ? html`<p class="product-card__cat">${p.category.name}</p>` : ''}
      <h3 class="product-card__title"><a href="/producto/${p.slug}" data-link>${p.name}</a></h3>
      ${price(p)}
      <div class="product-card__meta">${availability(p)} ${demoBadge(p)}</div>
      <button type="button" class="btn btn--secondary btn--block product-card__add" data-action="add-to-cart" data-id="${p.id}" ${out ? 'disabled' : ''}>
        ${out ? 'Agotado' : 'Agregar al carrito'}
      </button>
    </div>
  </article>`;
}

export const productGrid = (items) => html`<div class="product-grid">${items.map(productCard)}</div>`;
