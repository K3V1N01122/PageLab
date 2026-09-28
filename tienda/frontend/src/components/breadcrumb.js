import { html } from '../utils/html.js';

export const breadcrumb = (items) => html`
  <nav class="breadcrumb" aria-label="Ruta de navegación"><ol>
    <li><a href="/" data-link>Inicio</a></li>
    ${items.map((it, i) => html`<li>${i === items.length - 1 && !it.link
      ? html`<span aria-current="page">${it.name}</span>`
      : html`<a href="${it.href}" data-link>${it.name}</a>`}</li>`)}
  </ol></nav>`;
