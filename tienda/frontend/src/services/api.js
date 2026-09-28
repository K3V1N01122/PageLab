/**
 * Cliente HTTP de la API.
 * - Envía cookies de sesión y el token CSRF (doble envío).
 * - Normaliza errores: el usuario nunca ve mensajes técnicos.
 */
const BASE = '/api/v1';
const TIMEOUT_MS = 15000;

export class ApiError extends Error {
  constructor(status, code, message, details) {
    super(message);
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

function csrfToken() {
  const m = document.cookie.match(/(?:^|;\s*)csrf_token=([^;]+)/);
  return m ? decodeURIComponent(m[1]) : '';
}

async function ensureCsrf() {
  if (!csrfToken()) await fetch(`${BASE}/health`, { credentials: 'same-origin' });
}

export async function request(method, path, { body, query, form } = {}) {
  const url = new URL(BASE + path, location.origin);
  if (query) Object.entries(query).forEach(([k, v]) => { if (v !== undefined && v !== null && v !== '') url.searchParams.set(k, v); });
  const headers = { Accept: 'application/json' };
  const unsafe = method !== 'GET';
  if (unsafe) {
    await ensureCsrf();
    headers['X-CSRF-Token'] = csrfToken();
  }
  let payload;
  if (form) payload = form;
  else if (body !== undefined) { headers['Content-Type'] = 'application/json'; payload = JSON.stringify(body); }
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), TIMEOUT_MS);
  let res;
  try {
    res = await fetch(url, { method, headers, body: payload, credentials: 'same-origin', signal: ctrl.signal });
  } catch (err) {
    throw new ApiError(0, 'network_error', err.name === 'AbortError'
      ? 'El servidor tardó demasiado en responder. Inténtalo de nuevo.'
      : 'No hay conexión con el servidor. Revisa tu internet e inténtalo de nuevo.');
  } finally {
    clearTimeout(timer);
  }
  let data = null;
  try { data = await res.json(); } catch { /* respuesta sin JSON */ }
  if (!res.ok) {
    const e = data?.error || {};
    throw new ApiError(res.status, e.code || 'error', e.message || 'No se pudo completar la operación.', e.details);
  }
  return data;
}

export const api = {
  get: (p, query) => request('GET', p, { query }),
  post: (p, body) => request('POST', p, { body: body ?? {} }),
  put: (p, body) => request('PUT', p, { body: body ?? {} }),
  patch: (p, body) => request('PATCH', p, { body: body ?? {} }),
  del: (p) => request('DELETE', p),
  upload: (p, file) => { const f = new FormData(); f.append('file', file); return request('POST', p, { form: f }); },
};
