/**
 * Panel de administración: SPA separada de la tienda (/admin).
 * El menú se filtra por permisos solo por comodidad: el backend valida cada
 * acción de forma independiente.
 */
import { html, render, $ } from '../utils/html.js';
import { api } from '../services/api.js';
import { store } from '../store/store.js';
import { toastError } from '../components/toast.js';

const root = document.getElementById('admin-root');

const SECTIONS = [
  { path: '/admin', label: 'Resumen', perm: 'stats.read', load: () => import('./pages/dashboard.js') },
  { path: '/admin/pedidos', label: 'Pedidos', perm: 'orders.read', load: () => import('./pages/orders.js') },
  { path: '/admin/productos', label: 'Productos', perm: 'products.read', load: () => import('./pages/products.js') },
  { path: '/admin/categorias', label: 'Categorías', perm: 'products.read', load: () => import('./pages/categories.js') },
  { path: '/admin/usuarios', label: 'Clientes y usuarios', perm: 'users.read', load: () => import('./pages/users.js') },
  { path: '/admin/fidelizacion', label: 'Fidelización', perm: 'loyalty.manage', load: () => import('./pages/loyalty.js') },
  { path: '/admin/promociones', label: 'Cupones y promociones', perm: 'promotions.manage', load: () => import('./pages/promotions.js') },
  { path: '/admin/configuracion', label: 'Configuración', perm: 'settings.manage', load: () => import('./pages/settings.js') },
];

export const can = (perm) => store.get().user?.permissions.includes(perm);

let content;
let token = 0;

export function go(path, replace = false) {
  history[replace ? 'replaceState' : 'pushState']({}, '', path);
  resolve();
}

async function resolve() {
  const my = ++token;
  const path = location.pathname.replace(/\/$/, '') || '/admin';
  const allowed = SECTIONS.filter((s) => can(s.perm));
  // Sección más específica que coincide con la ruta (p. ej. /admin/pedidos/15).
  const section = [...allowed].sort((a, b) => b.path.length - a.path.length)
    .find((s) => path === s.path || path.startsWith(`${s.path}/`)) || (path === '/admin' ? allowed[0] : null);
  root.querySelectorAll('.a-nav a').forEach((a) => {
    const active = section && a.getAttribute('href') === section.path;
    if (active) a.setAttribute('aria-current', 'page'); else a.removeAttribute('aria-current');
  });
  if (!section) { render(content, html`<div class="state"><h1 class="state__title">Sección no disponible</h1><p>No existe o tu rol no tiene acceso.</p></div>`); return; }
  render(content, html`<div class="state state--loading" role="status"><span class="spinner" aria-hidden="true"></span><span>Cargando…</span></div>`);
  try {
    const mod = await section.load();
    if (my !== token) return;
    const sub = path.slice(section.path.length).split('/').filter(Boolean);
    await mod.default(content, { sub, query: new URLSearchParams(location.search) });
    document.title = `${section.label} | Panel`;
    content.querySelector('h1')?.focus({ preventScroll: true });
  } catch (err) {
    console.error(err);
    render(content, html`<div class="state state--error" role="alert"><h1 class="state__title">No se pudo cargar esta sección</h1><p>${err.message || ''}</p></div>`);
  }
  window.scrollTo({ top: 0 });
}

async function boot() {
  try {
    const [{ user }, config] = await Promise.all([api.get('/admin/me'), api.get('/config')]);
    store.set({ user, config });
  } catch (err) {
    if (err.status === 401) { location.href = `/iniciar-sesion?next=${encodeURIComponent(location.pathname)}`; return; }
    render(root, html`<div class="state state--error"><h1 class="state__title">${err.status === 403 ? 'No tienes acceso al panel' : 'No se pudo abrir el panel'}</h1>
      <p>${err.message}</p><a class="btn btn--primary" href="/">Volver a la tienda</a></div>`);
    return;
  }
  const { user, config } = store.get();
  const items = SECTIONS.filter((s) => can(s.perm));
  render(root, html`
    <a class="skip-link" href="#a-content">Saltar al contenido</a>
    <aside class="a-side">
      <a class="a-brand" href="/admin">${config.store.name}<small>Panel de administración</small></a>
      <nav class="a-nav" aria-label="Secciones del panel"><ul>${items.map((s) => html`<li><a href="${s.path}">${s.label}</a></li>`)}</ul></nav>
      <div class="a-user"><p>${user.first_name} ${user.last_name}<br><small>${user.role}</small></p>
        <a href="/" class="a-link">Ver tienda</a> <button type="button" class="linklike" data-logout>Cerrar sesión</button></div>
    </aside>
    <main id="a-content" class="a-content" tabindex="-1"></main>`);
  content = $('#a-content', root);
  root.addEventListener('click', (e) => {
    const a = e.target.closest('a[href^="/admin"]');
    if (a && !e.metaKey && !e.ctrlKey && a.target !== '_blank') { e.preventDefault(); go(a.getAttribute('href')); }
  });
  $('[data-logout]', root).addEventListener('click', async () => {
    try { await api.post('/auth/logout'); location.href = '/'; } catch (err) { toastError(err); }
  });
  window.addEventListener('popstate', resolve);
  resolve();
}

boot();
