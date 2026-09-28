/**
 * Carrito.
 * - Invitado: en localStorage se guardan SOLO ids y cantidades (nunca precios).
 * - Con sesión: el carrito vive en el servidor; al iniciar sesión se fusiona.
 * Los precios y totales siempre los calcula el backend.
 */
import { api } from './api.js';
import { store } from '../store/store.js';

const KEY = 'cart:v1';
const MAX_QTY = 99;

function readGuest() {
  try {
    const items = JSON.parse(localStorage.getItem(KEY) || '[]');
    return Array.isArray(items) ? items.filter((i) => Number.isInteger(i.product_id) && Number.isInteger(i.quantity)) : [];
  } catch { return []; }
}

function writeGuest(items) {
  try { localStorage.setItem(KEY, JSON.stringify(items)); } catch { /* almacenamiento lleno o bloqueado */ }
  store.set({ cartCount: items.reduce((n, i) => n + i.quantity, 0) });
}

const loggedIn = () => !!store.get().user;
const countFrom = (quote) => { store.set({ cartCount: quote.item_count || 0 }); return quote; };

export const cart = {
  async get() {
    if (loggedIn()) return countFrom(await api.get('/cart'));
    const quote = await api.post('/cart/quote', { items: readGuest() });
    // Si algún producto dejó de existir, se limpia del navegador.
    const valid = new Set(quote.lines.map((l) => l.product_id));
    const outOfStock = new Set(quote.issues.filter((i) => i.code === 'out_of_stock' || i.code === 'unavailable').map((i) => i.product_id));
    writeGuest(readGuest().filter((i) => valid.has(i.product_id) || outOfStock.has(i.product_id)));
    return quote;
  },
  async add(productId, quantity = 1) {
    if (loggedIn()) return countFrom(await api.post('/cart/items', { product_id: productId, quantity }));
    const items = readGuest();
    const line = items.find((i) => i.product_id === productId);
    const next = Math.min((line?.quantity || 0) + quantity, MAX_QTY);
    // Validación de stock en el servidor antes de guardar.
    const quote = await api.post('/cart/quote', { items: [{ product_id: productId, quantity: next }] });
    const issue = quote.issues.find((i) => i.product_id === productId);
    if (issue) {
      const err = new Error(issue.message);
      err.code = issue.code;
      throw err;
    }
    if (line) line.quantity = next; else items.push({ product_id: productId, quantity });
    writeGuest(items);
    return quote;
  },
  async setQty(productId, quantity) {
    if (loggedIn()) return countFrom(await api.put(`/cart/items/${productId}`, { quantity }));
    const items = readGuest().map((i) => (i.product_id === productId ? { ...i, quantity } : i)).filter((i) => i.quantity > 0);
    writeGuest(items);
    return this.get();
  },
  async remove(productId) {
    if (loggedIn()) return countFrom(await api.del(`/cart/items/${productId}`));
    writeGuest(readGuest().filter((i) => i.product_id !== productId));
    return this.get();
  },
  preview: (opts) => api.post('/cart/preview', opts).then(countFrom),
  async mergeGuest() {
    const items = readGuest();
    if (items.length) {
      try { await api.post('/cart/merge', { items }); localStorage.removeItem(KEY); } catch { /* se reintenta luego */ }
    }
    return this.refreshCount();
  },
  async refreshCount() {
    if (!loggedIn()) { writeGuest(readGuest()); return; }
    try { countFrom(await api.get('/cart')); } catch { /* sin conexión: se mantiene el contador */ }
  },
};
