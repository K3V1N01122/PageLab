/**
 * Plantillas HTML seguras.
 * Todo valor interpolado se escapa automáticamente (protección XSS).
 * Para insertar HTML ya seguro (otra plantilla) se pasa un SafeHtml.
 */
export class SafeHtml {
  constructor(value) { this.value = value; }
  toString() { return this.value; }
}

const ESC = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;', '`': '&#96;' };
export const escape = (v) => String(v ?? '').replace(/[&<>"'`]/g, (c) => ESC[c]);

function toHtml(value) {
  if (value === null || value === undefined || value === false) return '';
  if (value instanceof SafeHtml) return value.value;
  if (Array.isArray(value)) return value.map(toHtml).join('');
  return escape(value);
}

export function html(strings, ...values) {
  let out = strings[0];
  values.forEach((v, i) => { out += toHtml(v) + strings[i + 1]; });
  return new SafeHtml(out);
}

/** Solo para cadenas generadas por el propio código (iconos SVG), nunca datos del usuario. */
export const trusted = (s) => new SafeHtml(s);

export function render(el, tpl) {
  el.innerHTML = toHtml(tpl);
  return el;
}

export const $ = (sel, root = document) => root.querySelector(sel);
export const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];
