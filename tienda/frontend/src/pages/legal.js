import { html, render } from '../utils/html.js';
import { store } from '../store/store.js';
import { setTitle } from '../router.js';

/** Textos legales: PENDIENTES de redactar por el cliente/asesor legal. */
export default async function legal(el, ctx) {
  const terms = ctx.path.startsWith('/terminos');
  const title = terms ? 'Términos y condiciones' : 'Política de privacidad';
  setTitle(title);
  render(el, html`
    <div class="container narrow prose">
      <h1 class="page-title">${title}</h1>
      <div class="notice notice--warn"><p>Este texto es un marcador de posición. ${store.get().config.store.name} debe reemplazarlo por el documento legal definitivo antes de publicar la tienda.</p></div>
      <p>Aquí se describirán ${terms ? 'las condiciones de compra, envíos, devoluciones, garantías y el funcionamiento del programa de puntos' : 'los datos personales que se recopilan, su finalidad, el tiempo de conservación y cómo ejercer tus derechos sobre ellos'}.</p>
    </div>`);
}
