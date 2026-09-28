import { html } from '../utils/html.js';

/** Paginación con enlaces reales (navegables y rastreables). */
export function pagination({ page, pages }, hrefFor) {
  if (pages <= 1) return '';
  const nums = new Set([1, pages, page - 1, page, page + 1].filter((n) => n >= 1 && n <= pages));
  const list = [...nums].sort((a, b) => a - b);
  const items = [];
  list.forEach((n, i) => {
    if (i && n - list[i - 1] > 1) items.push(html`<li aria-hidden="true" class="pagination__gap">…</li>`);
    items.push(html`<li><a href="${hrefFor(n)}" data-link class="pagination__link" ${n === page ? html`aria-current="page"` : ''}>${n}</a></li>`);
  });
  return html`
    <nav class="pagination" aria-label="Paginación">
      <a class="pagination__link" href="${hrefFor(Math.max(1, page - 1))}" data-link ${page === 1 ? html`aria-disabled="true" tabindex="-1"` : ''}>Anterior</a>
      <ol>${items}</ol>
      <a class="pagination__link" href="${hrefFor(Math.min(pages, page + 1))}" data-link ${page === pages ? html`aria-disabled="true" tabindex="-1"` : ''}>Siguiente</a>
    </nav>`;
}
