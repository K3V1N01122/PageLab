import { html, render } from '../utils/html.js';
import { store } from '../store/store.js';
import { setTitle } from '../router.js';
import { contactLinks } from '../components/footer.js';
import { icons } from '../components/icons.js';

export default async function contact(el) {
  setTitle('Contacto');
  const { config } = store.get();
  const c = config.contact || {};
  const { items, nets } = contactLinks(c, config.social);
  render(el, html`
    <div class="container narrow">
      <h1 class="page-title">Contacto</h1>
      <p class="page-lead">Escríbenos por el medio que prefieras.</p>
      ${items.length || c.address || c.hours ? html`<ul class="contact-list">
        ${items.map((i) => html`<li><a href="${i.href}" ${i.ext ? html`target="_blank" rel="noopener noreferrer"` : ''}>${i.icon}<span>${i.label}</span></a></li>`)}
        ${c.address ? html`<li>${icons.pin}<span>${c.address}</span></li>` : ''}
        ${c.hours ? html`<li>${icons.clock}<span>${c.hours}</span></li>` : ''}
      </ul>` : html`<div class="notice notice--info"><p>Los datos de contacto aún no están configurados. El administrador puede agregarlos en Panel &gt; Configuración &gt; Contacto.</p></div>`}
      ${nets.length ? html`<h2 class="section__title">Redes sociales</h2><ul class="contact-list">${nets.map((n) => html`
        <li><a href="${n.href}" target="_blank" rel="noopener noreferrer">${n.icon}<span>${n.label}</span></a></li>`)}</ul>` : ''}
    </div>`);
}
