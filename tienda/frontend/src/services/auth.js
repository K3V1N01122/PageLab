import { api } from './api.js';
import { store } from '../store/store.js';
import { cart } from './cart.js';

export const auth = {
  async loadMe() {
    const { user } = await api.get('/auth/me');
    store.set({ user });
    return user;
  },
  async login(data) {
    const { user } = await api.post('/auth/login', data);
    store.set({ user });
    await cart.mergeGuest();
    await loadFavorites();
    return user;
  },
  async register(data) {
    const { user } = await api.post('/auth/register', data);
    store.set({ user });
    await cart.mergeGuest();
    return user;
  },
  async logout() {
    await api.post('/auth/logout');
    store.set({ user: null, favorites: new Set() });
    await cart.refreshCount();
  },
  forgot: (email) => api.post('/auth/password/forgot', { email }),
  reset: (data) => api.post('/auth/password/reset', data),
  changePassword: (data) => api.post('/auth/password/change', data),
};

export async function loadFavorites() {
  if (!store.get().user) return;
  try {
    const { ids } = await api.get('/account/favorites');
    store.set({ favorites: new Set(ids) });
  } catch { /* no bloquea la navegación */ }
}

export async function toggleFavorite(productId) {
  const favs = new Set(store.get().favorites);
  if (favs.has(productId)) {
    await api.del(`/account/favorites/${productId}`);
    favs.delete(productId);
  } else {
    await api.post(`/account/favorites/${productId}`);
    favs.add(productId);
  }
  store.set({ favorites: favs });
  return favs.has(productId);
}
