import { html, render } from '../utils/html.js';
import { api } from '../services/api.js';
import { store } from '../store/store.js';
import { setTitle } from '../router.js';
import { money, number } from '../utils/format.js';
import { productGrid } from '../components/productCard.js';
import { loyaltyCard } from '../components/loyaltyCard.js';
import { skeletonGrid } from '../components/states.js';
import { icons } from '../components/icons.js';
import { contactLinks } from '../components/footer.js';

const section = (id, title, link, body) => html`
  <section class="section" aria-labelledby="${id}">
    <div class="section__head">
      <h2 id="${id}" class="section__title">${title}</h2>
      ${link ? html`<a class="link-more" href="${link.href}" data-link>${link.label}</a>` : ''}
    </div>
    <div data-slot="${id}">${body}</div>
  </section>`;

export default async function home(el) {
  const { config, user } = store.get();
  const s = config.store;
  const l = config.loyalty;
  const contact = contactLinks(config.contact, config.social);
  setTitle(config.seo?.default_title || s.name);
  render(el, html`
    <section class="hero">
      <div class="container hero__inner">
        <div class="hero__copy">
          <h1 class="hero__title">${s.name}</h1>
          <p class="hero__lead">${s.tagline}</p>
          <div class="hero__actions">
            <a class="btn btn--primary btn--lg" href="/catalogo" data-link>Ver catálogo</a>
            ${l.enabled ? html`<a class="btn btn--ghost btn--lg" href="/puntos" data-link>Cómo funcionan los puntos</a>` : ''}
          </div>
        </div>
        ${l.enabled ? html`<div class="hero__card">${loyaltyCard(null)}
          <p class="hero__card-note">Cada ${money(100)} de compra suma ${number(l.points_per_currency_unit)} ${l.points_per_currency_unit === 1 ? 'punto' : 'puntos'}.</p></div>` : ''}
      </div>
    </section>
    <div class="container">
      <section class="section" aria-labelledby="h-cats">
        <h2 id="h-cats" class="section__title">Categorías</h2>
        <ul class="category-strip" data-slot="cats"></ul>
      </section>
      ${section('h-featured', 'Destacados', { href: '/catalogo', label: 'Ver todo' }, skeletonGrid(4))}
      ${section('h-sale', 'Ofertas', { href: '/ofertas', label: 'Ver ofertas' }, skeletonGrid(4))}
      ${section('h-new', 'Recién llegados', { href: '/catalogo?sort=newest', label: 'Ver novedades' }, skeletonGrid(4))}
      <section class="benefits" aria-label="Beneficios de comprar aquí">
        <div class="benefit">${icons.truck}<div><h3>Entrega o recogida</h3><p>${config.shipping_methods.map((m) => m.label).join(' o ')}.</p></div></div>
        <div class="benefit">${icons.wallet}<div><h3>Formas de pago</h3><p>${config.payment_providers.map((p) => p.label).join(', ')}.</p></div></div>
        <div class="benefit">${icons.shield}<div><h3>Compra protegida</h3><p>Precios y existencias confirmados antes de cerrar tu pedido.</p></div></div>
      </section>
      ${l.enabled ? html`
      <section class="points-band" aria-labelledby="h-points">
        <div>
          <h2 id="h-points" class="section__title">${l.program_name}</h2>
          <p>Tu tarjeta virtual se crea al registrarte. Acumulas puntos con cada compra entregada y los canjeas por descuentos, cupones y recompensas.</p>
          <p class="points-band__rule">${number(l.redeem_block_points)} puntos equivalen a ${money(l.redeem_block_value_cents)} de descuento.</p>
        </div>
        <a class="btn btn--brass" href="${user ? '/cuenta/puntos' : '/registro'}" data-link>${user ? 'Ver mis puntos' : 'Crear cuenta'}</a>
      </section>` : ''}
      ${contact.items.length ? html`
      <section class="section contact-strip" aria-labelledby="h-contact">
        <h2 id="h-contact" class="section__title">¿Tienes preguntas?</h2>
        <ul>${contact.items.map((i) => html`<li><a href="${i.href}" ${i.ext ? html`target="_blank" rel="noopener noreferrer"` : ''}>${i.icon}<span>${i.label}</span></a></li>`)}</ul>
      </section>` : ''}
    </div>`);

  const slot = (id) => el.querySelector(`[data-slot="${id}"]`);
  const cats = await api.get('/categories').then((r) => r.items).catch(() => []);
  render(slot('cats'), cats.map((c) => html`
    <li><a href="/categoria/${c.slug}" data-link class="category-chip"><span>${c.name}</span><small>${c.total_count} ${c.total_count === 1 ? 'producto' : 'productos'}</small></a></li>`));

  const load = async (id, query, fallback) => {
    try {
      const { items } = await api.get('/products', { page_size: 4, ...query });
      render(slot(id), items.length ? productGrid(items) : html`<p class="muted">${fallback}</p>`);
    } catch {
      render(slot(id), html`<p class="muted">No pudimos cargar estos productos. Recarga la página para intentarlo de nuevo.</p>`);
    }
  };
  await Promise.all([
    load('h-featured', { featured: 1 }, 'Aún no hay productos destacados.'),
    load('h-sale', { on_sale: 1 }, 'No hay ofertas activas en este momento.'),
    load('h-new', { sort: 'newest' }, 'Aún no hay productos publicados.'),
  ]);
}
