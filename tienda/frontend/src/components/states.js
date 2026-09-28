import { html } from '../utils/html.js';

export const loading = (label = 'Cargando…') => html`
  <div class="state state--loading" role="status" aria-live="polite"><span class="spinner" aria-hidden="true"></span><span>${label}</span></div>`;

export const empty = (title, text, action) => html`
  <div class="state state--empty">
    <h2 class="state__title">${title}</h2>
    ${text ? html`<p>${text}</p>` : ''}
    ${action ? html`<a class="btn btn--primary" href="${action.href}" data-link>${action.label}</a>` : ''}
  </div>`;

export const errorState = (err, retry = true) => html`
  <div class="state state--error" role="alert">
    <h2 class="state__title">No pudimos cargar esta sección</h2>
    <p>${err?.message || 'Ocurrió un problema inesperado.'}</p>
    ${retry ? html`<button type="button" class="btn btn--secondary" data-action="retry">Reintentar</button>` : ''}
  </div>`;

export const skeletonGrid = (n = 8) => html`
  <div class="product-grid" aria-hidden="true">${Array.from({ length: n }, () => html`
    <div class="skeleton-card"><div class="skeleton skeleton--img"></div><div class="skeleton skeleton--line"></div><div class="skeleton skeleton--line short"></div></div>`)}</div>`;
