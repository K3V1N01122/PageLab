import { html, render, $$ } from '../utils/html.js';
import { api } from '../services/api.js';
import { store } from '../store/store.js';
import { setTitle } from '../router.js';
import { money, number, uid, date } from '../utils/format.js';
import { loyaltyCard } from '../components/loyaltyCard.js';
import { toast, toastError } from '../components/toast.js';

const KIND = { fixed_discount: 'Descuento', percent_discount: 'Descuento', free_shipping: 'Envío', free_product: 'Producto' };

export default async function rewards(el) {
  const { config, user } = store.get();
  const l = config.loyalty;
  setTitle(l.program_name);
  const [{ items }, card] = await Promise.all([api.get('/rewards'), user ? api.get('/loyalty/card') : Promise.resolve(null)]);
  const draw = (card) => {
    render(el, html`
      <div class="container rewards-page">
        <header class="rewards-head">
          <div>
            <h1 class="page-title">${l.program_name}</h1>
            <p class="page-lead">Suma puntos con cada compra y cámbialos por descuentos y beneficios en la tienda.</p>
            <ol class="how">
              <li><strong>Regístrate</strong><span>Tu tarjeta virtual se crea automáticamente.</span></li>
              <li><strong>Compra</strong><span>Ganas ${number(l.points_per_currency_unit)} ${l.points_per_currency_unit === 1 ? 'punto' : 'puntos'} por cada ${money(100)}. Se acreditan cuando recibes tu pedido.</span></li>
              <li><strong>Canjea</strong><span>${number(l.redeem_block_points)} puntos = ${money(l.redeem_block_value_cents)} en el checkout, o elige una recompensa.</span></li>
            </ol>
          </div>
          ${loyaltyCard(card)}
        </header>
        <section aria-labelledby="h-rewards">
          <h2 id="h-rewards" class="section__title">Recompensas disponibles</h2>
          ${items.length ? html`<ul class="reward-list">${items.map((r) => {
            const affordable = card && card.points_available >= r.points_cost;
            return html`<li class="reward">
              <p class="reward__kind">${KIND[r.kind] || 'Beneficio'}</p>
              <h3 class="reward__name">${r.name}</h3>
              ${r.description ? html`<p class="reward__desc">${r.description}</p>` : ''}
              <p class="reward__cost">${number(r.points_cost)} puntos</p>
              ${user ? html`<button type="button" class="btn ${affordable ? 'btn--brass' : 'btn--ghost'}" data-redeem="${r.id}" data-cost="${r.points_cost}" data-name="${r.name}" ${affordable ? '' : 'disabled'}>
                ${affordable ? 'Canjear' : `Te faltan ${number(r.points_cost - card.points_available)} puntos`}</button>`
                : html`<a class="btn btn--ghost" href="/iniciar-sesion?next=/recompensas" data-link>Inicia sesión para canjear</a>`}
            </li>`;
          })}</ul>` : html`<p class="muted">Pronto habrá recompensas disponibles.</p>`}
        </section>
        <div data-slot="result" aria-live="polite"></div>
      </div>`);
    $$('[data-redeem]', el).forEach((b) => b.addEventListener('click', async () => {
      if (!confirm(`¿Canjear "${b.dataset.name}" por ${number(+b.dataset.cost)} puntos?`)) return;
      b.disabled = true;
      // Una clave por intento: si la red reintenta, el backend no descuenta dos veces.
      const key = uid();
      try {
        const r = await api.post(`/rewards/${b.dataset.redeem}/redeem`, { idempotency_key: key });
        const fresh = await api.get('/loyalty/card');
        draw(fresh);
        render(el.querySelector('[data-slot="result"]'), html`
          <div class="notice notice--success" role="status">
            <p><strong>Canje realizado.</strong> Usaste ${number(r.points_spent)} puntos en ${r.reward}.</p>
            ${r.coupon_code ? html`<p>Tu cupón es <span class="coupon-code">${r.coupon_code}</span>. Úsalo en el carrito antes del ${date(r.coupon_expires_at)}.</p>` : ''}
          </div>`);
        el.querySelector('[data-slot="result"]').scrollIntoView({ behavior: 'smooth', block: 'center' });
        toast('Canje realizado.');
      } catch (err) { toastError(err); b.disabled = false; }
    }));
  };
  draw(card);
}
