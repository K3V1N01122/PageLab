import { store } from '../store/store.js';

let moneyFmt = null;
let fmtKey = '';

/** Montos siempre en centavos (enteros), igual que el backend. */
export function money(cents) {
  const s = store.get().config?.store || {};
  const key = `${s.locale}|${s.currency}`;
  if (!moneyFmt || key !== fmtKey) {
    try {
      moneyFmt = new Intl.NumberFormat(s.locale || 'es-GT', { style: 'currency', currency: s.currency || 'GTQ' });
    } catch {
      moneyFmt = new Intl.NumberFormat('es-GT', { style: 'currency', currency: 'GTQ' });
    }
    fmtKey = key;
  }
  return moneyFmt.format((cents || 0) / 100);
}

export const number = (n) => new Intl.NumberFormat('es-GT').format(n || 0);

export function date(iso, opts = { dateStyle: 'medium' }) {
  if (!iso) return '';
  try { return new Intl.DateTimeFormat('es-GT', opts).format(new Date(iso)); } catch { return iso; }
}

export const dateTime = (iso) => date(iso, { dateStyle: 'medium', timeStyle: 'short' });

export function plural(n, one, many) { return `${number(n)} ${n === 1 ? one : many}`; }

export function uid() {
  if (crypto.randomUUID) return crypto.randomUUID().replace(/-/g, '');
  const a = new Uint8Array(16);
  crypto.getRandomValues(a);
  return [...a].map((b) => b.toString(16).padStart(2, '0')).join('');
}
