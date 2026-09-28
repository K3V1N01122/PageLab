/** Piezas de interfaz del panel (reutilizan las utilidades de la tienda). */
import { html } from '../utils/html.js';
import { money } from '../utils/format.js';

export const pageHead = (title, actions = '') => html`<header class="a-head"><h1 class="a-title">${title}</h1><div class="a-head__actions">${actions}</div></header>`;

export const input = (name, label, value = '', { type = 'text', required = false, help = '', attrs = '', optional = false } = {}) => html`
  <div class="field"><label for="f-${name}">${label}${optional ? html` <span class="optional">(opcional)</span>` : ''}</label>
    <input id="f-${name}" name="${name}" type="${type}" value="${value ?? ''}" ${required ? 'required' : ''} ${attrs}>
    ${help ? html`<p class="help">${help}</p>` : ''}</div>`;

/** Campo de dinero: se muestra en quetzales y se envía en centavos (data-type="money"). */
export const moneyInput = (name, label, cents, opts = {}) => input(name, label, cents === null || cents === undefined ? '' : (cents / 100).toFixed(2),
  { ...opts, type: 'number', attrs: html`step="0.01" min="0" data-type="money" inputmode="decimal"` });

export const intInput = (name, label, value, opts = {}) => input(name, label, value, { ...opts, type: 'number', attrs: html`step="1" data-type="int" inputmode="numeric" ${opts.min !== undefined ? html`min="${opts.min}"` : ''}` });

export const select = (name, label, options, value, { optional = false, empty = null } = {}) => html`
  <div class="field"><label for="f-${name}">${label}${optional ? html` <span class="optional">(opcional)</span>` : ''}</label>
    <select id="f-${name}" name="${name}" ${options.some(([v]) => typeof v === 'number') ? html`data-type="int"` : ''}>
      ${empty !== null ? html`<option value="">${empty}</option>` : ''}
      ${options.map(([v, l]) => html`<option value="${v}" ${String(v) === String(value ?? '') ? 'selected' : ''}>${l}</option>`)}
    </select></div>`;

export const checkbox = (name, label, checked) => html`<label class="check"><input type="checkbox" name="${name}" ${checked ? 'checked' : ''}> ${label}</label>`;

export const textarea = (name, label, value = '', rows = 4, optional = true) => html`
  <div class="field"><label for="f-${name}">${label}${optional ? html` <span class="optional">(opcional)</span>` : ''}</label>
    <textarea id="f-${name}" name="${name}" rows="${rows}">${value ?? ''}</textarea></div>`;

export const dateOnly = (iso) => (iso ? String(iso).slice(0, 10) : '');

export const kpi = (label, value, note = '') => html`<div class="kpi"><p class="kpi__label">${label}</p><p class="kpi__value">${value}</p>${note ? html`<p class="kpi__note">${note}</p>` : ''}</div>`;

export const moneyCell = (c) => html`<td class="num">${money(c)}</td>`;

export const yesNo = (v) => (v ? 'Sí' : 'No');
