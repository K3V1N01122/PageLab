import { render } from '../../utils/html.js';
import { api } from '../../services/api.js';
import { setTitle } from '../../router.js';
import { productGrid } from '../../components/productCard.js';
import { empty } from '../../components/states.js';
import { accountLayout, bindLayout } from './layout.js';

export default async function favorites(el) {
  setTitle('Favoritos');
  const { items } = await api.get('/account/favorites');
  render(el, accountLayout('/cuenta/favoritos', 'Favoritos', items.length ? productGrid(items)
    : empty('Aún no guardas favoritos', 'Toca el corazón en cualquier producto para guardarlo aquí.', { href: '/catalogo', label: 'Ver catálogo' })));
  bindLayout(el);
}
