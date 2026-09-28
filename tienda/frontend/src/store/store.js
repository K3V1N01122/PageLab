/** Estado global mínimo con suscripción (sin dependencias). */
const state = { config: null, user: null, cartCount: 0, favorites: new Set() };
const listeners = new Set();

export const store = {
  get: () => state,
  set(patch) {
    Object.assign(state, patch);
    listeners.forEach((fn) => fn(state));
  },
  subscribe(fn) { listeners.add(fn); return () => listeners.delete(fn); },
};
