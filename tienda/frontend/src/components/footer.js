import { html, render } from '../utils/html.js';
import { store } from '../store/store.js';
import { icons } from './icons.js';

/** Enlaces de contacto y redes: vienen de la configuración central (panel > Configuración). */
export function contactLinks(contact = {}, social = {}) {
  const wa = contact.whatsapp ? `https://wa.me/${String(contact.whatsapp).replace(/\D/g, '')}` : null;
  const items = [
    wa && { href: wa, icon: icons.whatsapp, label: `WhatsApp ${contact.whatsapp}`, ext: true },
    contact.phone && { href: `tel:${String(contact.phone).replace(/\s/g, '')}`, icon: icons.phone, label: contact.phone },
    contact.email && { href: `mailto:${contact.email}`, icon: icons.mail, label: contact.email },
  ].filter(Boolean);
  const nets = [
    social.instagram && { href: social.instagram, icon: icons.instagram, label: 'Instagram' },
    social.facebook && { href: social.facebook, icon: icons.facebook, label: 'Facebook' },
    social.tiktok && { href: social.tiktok, icon: icons.tiktok, label: 'TikTok' },
  ].filter(Boolean);
  return { items, nets };
}

export function renderFooter(el, categories = []) {
  const { config } = store.get();
  const s = config?.store || {};
  const { items, nets } = contactLinks(config?.contact, config?.social);
  const c = config?.contact || {};
  render(el, html`
    <div class="container footer__mark">
      <p class="footer__wordmark" data-split>${s.closing_line || s.name || 'Tienda'}</p>
    </div>
    <div class="container footer__grid">
      <section class="footer__brand">
        <p class="footer__name">${s.name || 'Tienda'}</p>
        <p class="footer__tagline">${s.tagline || ''}</p>
        ${nets.length ? html`<ul class="footer__social">${nets.map((n) => html`
          <li><a href="${n.href}" target="_blank" rel="noopener noreferrer" aria-label="${n.label}">${n.icon}</a></li>`)}</ul>` : ''}
      </section>
      <nav aria-label="Categorías del pie de página">
        <h2 class="footer__title">Comprar</h2>
        <ul>
          <li><a href="/catalogo" data-link>Catálogo</a></li>
          ${categories.slice(0, 5).map((cat) => html`<li><a href="/categoria/${cat.slug}" data-link>${cat.name}</a></li>`)}
          <li><a href="/ofertas" data-link>Ofertas</a></li>
        </ul>
      </nav>
      <nav aria-label="Ayuda">
        <h2 class="footer__title">Ayuda</h2>
        <ul>
          <li><a href="/cuenta/pedidos" data-link>Mis pedidos</a></li>
          <li><a href="/puntos" data-link>Programa de puntos</a></li>
          <li><a href="/contacto" data-link>Contacto</a></li>
          <li><a href="/terminos" data-link>Términos y condiciones</a></li>
          <li><a href="/privacidad" data-link>Privacidad</a></li>
        </ul>
      </nav>
      <section>
        <h2 class="footer__title">Contacto</h2>
        ${items.length || c.address || c.hours ? html`<ul class="footer__contact">
          ${items.map((i) => html`<li><a href="${i.href}" ${i.ext ? html`target="_blank" rel="noopener noreferrer"` : ''}>${i.icon}<span>${i.label}</span></a></li>`)}
          ${c.address ? html`<li>${icons.pin}<span>${c.address}</span></li>` : ''}
          ${c.hours ? html`<li>${icons.clock}<span>${c.hours}</span></li>` : ''}
        </ul>` : html`<p class="footer__muted">Los datos de contacto se configuran en el panel de administración.</p>`}
      </section>
    </div>
    <div class="container footer__legal">
      <p>© ${new Date().getFullYear()} ${s.name || 'Tienda'}. Todos los derechos reservados.</p>
    </div>`);
}
