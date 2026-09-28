import { route, startRouter, navigate } from './router.js';
import { store } from './store/store.js';
import { api } from './services/api.js';
import { auth, loadFavorites, toggleFavorite } from './services/auth.js';
import { cart } from './services/cart.js';
import { renderHeader, updateCartCount, closeMobileNav } from './components/header.js';
import { renderFooter } from './components/footer.js';
import { icons } from './components/icons.js';
import { toast, toastError } from './components/toast.js';

const header = document.getElementById('site-header');
const footer = document.getElementById('site-footer');
const main = document.getElementById('main');
let categories = [];

const requireAuth = () => (store.get().user ? null : `/iniciar-sesion?next=${encodeURIComponent(location.pathname + location.search)}`);
const guestOnly = () => (store.get().user ? '/cuenta' : null);

route('/', () => import('./pages/home.js'));
route('/catalogo', () => import('./pages/catalog.js'));
route('/buscar', () => import('./pages/catalog.js'));
route('/ofertas', () => import('./pages/catalog.js'));
route('/categoria/:slug', () => import('./pages/catalog.js'));
route('/producto/:slug', () => import('./pages/product.js'));
route('/carrito', () => import('./pages/cart.js'));
route('/checkout', () => import('./pages/checkout.js'), { guard: requireAuth });
route('/pedido/:number', () => import('./pages/orderConfirm.js'), { guard: requireAuth });
route('/iniciar-sesion', () => import('./pages/login.js'), { guard: guestOnly });
route('/registro', () => import('./pages/register.js'), { guard: guestOnly });
route('/recuperar-contrasena', () => import('./pages/forgot.js'));
route('/restablecer-contrasena', () => import('./pages/reset.js'));
route('/puntos', () => import('./pages/rewards.js'));
route('/recompensas', () => import('./pages/rewards.js'));
route('/contacto', () => import('./pages/contact.js'));
route('/terminos', () => import('./pages/legal.js'));
route('/privacidad', () => import('./pages/legal.js'));
route('/favoritos', () => import('./pages/account/favorites.js'), { guard: requireAuth });
route('/cuenta', () => import('./pages/account/overview.js'), { guard: requireAuth });
route('/cuenta/perfil', () => import('./pages/account/profile.js'), { guard: requireAuth });
route('/cuenta/direcciones', () => import('./pages/account/addresses.js'), { guard: requireAuth });
route('/cuenta/pedidos', () => import('./pages/account/orders.js'), { guard: requireAuth });
route('/cuenta/pedidos/:number', () => import('./pages/account/orderDetail.js'), { guard: requireAuth });
route('/cuenta/favoritos', () => import('./pages/account/favorites.js'), { guard: requireAuth });
route('/cuenta/puntos', () => import('./pages/account/points.js'), { guard: requireAuth });
route('/cuenta/seguridad', () => import('./pages/account/security.js'), { guard: requireAuth });
route('*', () => import('./pages/notFound.js'), { notFound: true });

function applyTheme(theme = {}) {
  const root = document.documentElement;
  // Colores configurables desde el panel. Solo se aceptan hex válidos.
  const map = { primary: '--ink', accent: '--accent', points: '--brass' };
  Object.entries(map).forEach(([k, v]) => { if (/^#[0-9a-f]{6}$/i.test(theme[k] || '')) root.style.setProperty(v, theme[k]); });
}

// Acciones globales delegadas (tarjetas de producto en cualquier página).
document.addEventListener('click', async (e) => {
  const btn = e.target.closest('[data-action]');
  if (!btn) return;
  const id = parseInt(btn.dataset.id, 10);
  if (btn.dataset.action === 'add-to-cart') {
    btn.disabled = true;
    try {
      await cart.add(id, 1);
      toast('Producto agregado al carrito.');
    } catch (err) { toastError(err); } finally { btn.disabled = false; }
  }
  if (btn.dataset.action === 'favorite') {
    if (!store.get().user) { navigate(`/iniciar-sesion?next=${encodeURIComponent(location.pathname)}`); return; }
    btn.disabled = true;
    try {
      const on = await toggleFavorite(id);
      btn.classList.toggle('is-active', on);
      btn.setAttribute('aria-pressed', String(on));
      btn.innerHTML = String(on ? icons.heartFill : icons.heart);
      toast(on ? 'Guardado en favoritos.' : 'Quitado de favoritos.');
    } catch (err) { toastError(err); } finally { btn.disabled = false; }
  }
});

async function boot() {
  try {
    const [config, cats] = await Promise.all([api.get('/config'), api.get('/categories'), auth.loadMe().catch(() => null)]);
    categories = cats.items;
    store.set({ config });
    window.__STORE_NAME__ = config.store?.name || '';
    applyTheme(config.theme);
  } catch (err) {
    main.innerHTML = '';
    const p = document.createElement('p');
    p.className = 'container state state--error';
    p.textContent = 'No pudimos conectar con la tienda. Revisa tu conexión y recarga la página.';
    main.appendChild(p);
    return;
  }
  renderHeader(header, categories);
  renderFooter(footer, categories);
  let lastUser = store.get().user?.id;
  store.subscribe((s) => {
    if (s.user?.id !== lastUser) { lastUser = s.user?.id; renderHeader(header, categories); } else updateCartCount(header);
  });
  await Promise.all([cart.refreshCount(), loadFavorites()]);
  startRouter(main, () => closeMobileNav(header));
}

window.addEventListener('unhandledrejection', (e) => { console.error(e.reason); });
boot();
