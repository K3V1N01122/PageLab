import { $, html, render } from '../utils/html.js';
import { store } from '../store/store.js';
import { icons } from './icons.js';
import { navigate } from '../router.js';
import { api } from '../services/api.js';

function logo(cfg) {
  const s = cfg?.store || {};
  return s.logo_url
    ? html`<img src="${s.logo_url}" alt="${s.name}" class="logo__img" height="36">`
    : html`<span class="logo__mark" aria-hidden="true">${(s.name || 'T').slice(0, 1)}</span><span class="logo__text">${s.name || 'Tienda'}</span>`;
}

function categoryLinks(categories) {
  return categories.slice(0, 7).map((c) => html`<li><a href="/categoria/${c.slug}" data-link>${c.name}</a></li>`);
}

export function renderHeader(el, categories = []) {
  const { config, user, cartCount } = store.get();
  const q = new URLSearchParams(location.search).get('q') || '';
  render(el, html`
    <a class="skip-link" href="#main">Saltar al contenido</a>
    <div class="header__bar container">
      <button type="button" class="icon-btn header__menu" data-action="menu" aria-expanded="false" aria-controls="site-nav" aria-label="Abrir menú">${icons.menu}</button>
      <a class="logo" href="/" data-link aria-label="${config?.store?.name || 'Tienda'}, inicio">${logo(config)}</a>
      <form class="search" role="search" action="/buscar" data-search>
        <label class="sr-only" for="search-q">Buscar productos</label>
        <input id="search-q" name="q" type="search" placeholder="Buscar productos" autocomplete="off" value="${q}"
          aria-autocomplete="list" aria-controls="search-suggest" maxlength="100">
        <button type="submit" class="search__btn" aria-label="Buscar">${icons.search}</button>
        <ul id="search-suggest" class="search__suggest" role="listbox" hidden></ul>
      </form>
      <nav class="header__actions" aria-label="Tu cuenta">
        ${user
          ? html`<a class="header__action" href="/cuenta" data-link>${icons.user}<span class="header__label">${user.first_name}</span></a>
                 <a class="header__action header__action--fav" href="/cuenta/favoritos" data-link aria-label="Favoritos">${icons.heart}</a>`
          : html`<a class="header__action" href="/iniciar-sesion" data-link>${icons.user}<span class="header__label">Iniciar sesión</span></a>`}
        <a class="header__action header__cart" href="/carrito" data-link aria-label="Carrito, ${cartCount} productos">
          ${icons.cart}<span class="cart-count ${cartCount ? '' : 'is-empty'}" aria-hidden="true">${cartCount}</span>
        </a>
      </nav>
    </div>
    <nav id="site-nav" class="site-nav" aria-label="Categorías">
      <div class="container site-nav__inner">
        <ul class="site-nav__list">
          <li><a href="/catalogo" data-link>Todo el catálogo</a></li>
          ${categoryLinks(categories)}
          <li><a href="/ofertas" data-link>Ofertas</a></li>
          ${config?.loyalty?.enabled ? html`<li><a href="/puntos" data-link class="site-nav__points">Puntos</a></li>` : ''}
        </ul>
        ${user?.is_staff ? html`<a class="site-nav__admin" href="/admin">Panel de administración</a>` : ''}
      </div>
    </nav>`);
  bindHeader(el);
}

let suggestTimer;
let docBound = false;
function bindHeader(el) {
  const form = $('[data-search]', el);
  const input = $('#search-q', el);
  const list = $('#search-suggest', el);
  form.addEventListener('submit', (e) => {
    e.preventDefault();
    const q = input.value.trim();
    list.hidden = true;
    navigate(q ? `/buscar?q=${encodeURIComponent(q)}` : '/catalogo');
  });
  input.addEventListener('input', () => {
    clearTimeout(suggestTimer);
    const q = input.value.trim();
    if (q.length < 2) { list.hidden = true; return; }
    suggestTimer = setTimeout(async () => {
      try {
        const { items } = await api.get('/search/suggest', { q });
        render(list, items.map((i) => html`<li role="option"><a href="/producto/${i.slug}" data-link>${i.name}</a></li>`));
        list.hidden = !items.length;
      } catch { list.hidden = true; }
    }, 250);
  });
  input.addEventListener('keydown', (e) => { if (e.key === 'Escape') list.hidden = true; });
  if (!docBound) {
    docBound = true;
    document.addEventListener('click', (e) => {
      const l = document.getElementById('search-suggest');
      if (l && !e.target.closest('[data-search]')) l.hidden = true;
    });
  }
  const menuBtn = $('[data-action="menu"]', el);
  menuBtn.addEventListener('click', () => {
    const open = el.classList.toggle('nav-open');
    menuBtn.setAttribute('aria-expanded', String(open));
    menuBtn.setAttribute('aria-label', open ? 'Cerrar menú' : 'Abrir menú');
  });
}

export function updateCartCount(el) {
  const { cartCount } = store.get();
  const badge = el.querySelector('.cart-count');
  const link = el.querySelector('.header__cart');
  if (!badge) return;
  badge.textContent = cartCount;
  badge.classList.toggle('is-empty', !cartCount);
  link.setAttribute('aria-label', `Carrito, ${cartCount} productos`);
}

export function closeMobileNav(el) {
  el.classList.remove('nav-open');
  $('[data-action="menu"]', el)?.setAttribute('aria-expanded', 'false');
}
