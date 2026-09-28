/** Mensajes breves de éxito o error, anunciados a lectores de pantalla. */
let region;

export function toast(message, type = 'success', timeout = 4000) {
  if (!region) {
    region = document.createElement('div');
    region.className = 'toasts';
    region.setAttribute('role', 'status');
    region.setAttribute('aria-live', 'polite');
    document.body.appendChild(region);
  }
  const el = document.createElement('div');
  el.className = `toast toast--${type}`;
  el.textContent = message;
  region.appendChild(el);
  setTimeout(() => { el.classList.add('is-leaving'); setTimeout(() => el.remove(), 250); }, timeout);
}

export const toastError = (err) => toast(err?.message || 'No se pudo completar la operación.', 'error', 6000);
