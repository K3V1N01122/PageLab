import { html } from '../utils/html.js';
import { money } from '../utils/format.js';

export const price = (p, size = '') => html`
  <p class="price ${size ? `price--${size}` : ''}">
    <span class="price__now ${p.compare_at_cents ? 'is-sale' : ''}">${money(p.price_cents)}</span>
    ${p.compare_at_cents ? html`<s class="price__was"><span class="sr-only">Precio anterior: </span>${money(p.compare_at_cents)}</s>` : ''}
  </p>`;

const AVAIL = {
  in_stock: ['Disponible', 'ok'],
  low_stock: ['Pocas unidades', 'low'],
  out_of_stock: ['Agotado', 'out'],
};

export const availability = (p, withCount = false) => {
  const [label, cls] = AVAIL[p.availability] || AVAIL.in_stock;
  const count = withCount && p.stock > 0 ? ` (${p.stock} en existencia)` : '';
  return html`<span class="avail avail--${cls}">${label}${count}</span>`;
};

export const demoBadge = (p) => (p.is_demo ? html`<span class="demo-badge" title="Producto de demostración, no es un producto real">Dato de prueba</span>` : '');
