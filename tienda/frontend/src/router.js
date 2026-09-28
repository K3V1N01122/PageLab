/**
 * Router del lado del cliente con URLs limpias (History API).
 * Las páginas se cargan bajo demanda (import dinámico) para que la carga
 * inicial solo incluya lo necesario.
 */
const routes = [];
let outlet;
let current = { cleanup: null, token: 0 };
let onNavigate = () => {};
let firstLoad = true;

export function route(pattern, loader, opts = {}) {
  const keys = [];
  if (opts.notFound) { routes.push({ regex: /(?!)/, keys, loader, ...opts }); return; }
  const regex = new RegExp('^' + pattern.replace(/\/:(\w+)/g, (_, k) => { keys.push(k); return '/([^/]+)'; }) + '/?$');
  routes.push({ regex, keys, loader, ...opts });
}

export function navigate(to, { replace = false } = {}) {
  const url = new URL(to, location.origin);
  // El panel es otra aplicación: se carga con navegación completa.
  if (url.origin !== location.origin || url.pathname.startsWith('/admin')) { location.href = to; return; }
  if (url.pathname + url.search === location.pathname + location.search && !url.hash) { resolve(); return; }
  history[replace ? 'replaceState' : 'pushState']({}, '', url.pathname + url.search + url.hash);
  resolve();
}

function match(path) {
  for (const r of routes) {
    const m = path.match(r.regex);
    if (m) return { r, params: Object.fromEntries(r.keys.map((k, i) => [k, decodeURIComponent(m[i + 1])])) };
  }
  return null;
}

export async function resolve() {
  const token = ++current.token;
  if (typeof current.cleanup === 'function') { try { current.cleanup(); } catch { /* noop */ } }
  current.cleanup = null;
  const path = location.pathname;
  const found = match(path) || { r: routes.find((x) => x.notFound), params: {} };
  const ctx = { path, params: found.params, query: new URLSearchParams(location.search) };
  onNavigate(ctx, found.r);
  try {
    if (found.r.guard) {
      const redirect = await found.r.guard(ctx);
      if (redirect) { navigate(redirect, { replace: true }); return; }
    }
    const mod = await found.r.loader();
    if (token !== current.token) return; // otra navegación empezó mientras cargaba
    outlet.setAttribute('aria-busy', 'true');
    current.cleanup = await mod.default(outlet, ctx);
  } catch (err) {
    console.error(err);
    if (token !== current.token) return;
    const mod = err?.status === 404 ? await import('./pages/notFound.js') : await import('./pages/error.js');
    await mod.default(outlet, { error: err });
  } finally {
    outlet.removeAttribute('aria-busy');
  }
  if (!location.hash) window.scrollTo({ top: 0 });
  // Accesibilidad: al cambiar de página, el foco va al título principal.
  const h1 = outlet.querySelector('h1');
  if (h1 && !firstLoad) { h1.setAttribute('tabindex', '-1'); h1.focus({ preventScroll: true }); }
  firstLoad = false;
}

export function startRouter(el, handler) {
  outlet = el;
  onNavigate = handler || onNavigate;
  document.addEventListener('click', (e) => {
    const a = e.target.closest('a[href]');
    if (!a || e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
    if (a.target === '_blank' || a.hasAttribute('download') || a.getAttribute('aria-disabled') === 'true') {
      if (a.getAttribute('aria-disabled') === 'true') e.preventDefault();
      return;
    }
    const url = new URL(a.href, location.origin);
    if (url.origin !== location.origin || url.pathname.startsWith('/api/') || url.pathname.startsWith('/admin') ||
        url.pathname.startsWith('/uploads/')) return;
    e.preventDefault();
    navigate(url.pathname + url.search + url.hash);
  });
  window.addEventListener('popstate', resolve);
  resolve();
}

export function setTitle(title) {
  const name = window.__STORE_NAME__ || '';
  document.title = title ? `${title}${name ? ` | ${name}` : ''}` : name;
}
