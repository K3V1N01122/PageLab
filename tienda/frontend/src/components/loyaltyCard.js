import { html } from '../utils/html.js';
import { money, number } from '../utils/format.js';
import { store } from '../store/store.js';

/** Tarjeta virtual de fidelidad. Con datos reales (card) o como muestra (sin card). */
export function loyaltyCard(card) {
  const cfg = store.get().config || {};
  const storeName = cfg.store?.name || 'Tienda';
  const program = card?.program_name || cfg.loyalty?.program_name || 'Programa de puntos';
  if (!card) {
    const l = cfg.loyalty || {};
    return html`
      <div class="loyalty-card loyalty-card--sample" aria-label="Ejemplo de tarjeta de puntos">
        <div class="loyalty-card__top"><span class="loyalty-card__store">${storeName}</span><span class="loyalty-card__program">${program}</span></div>
        <p class="loyalty-card__points"><span class="loyalty-card__num">${number(l.redeem_block_points || 1000)}</span> puntos</p>
        <p class="loyalty-card__rule">= ${money(l.redeem_block_value_cents || 5000)} de descuento</p>
        <div class="loyalty-card__bottom"><span>Tu nombre aquí</span><span class="loyalty-card__code">XXXX-XXXX-XXXX</span></div>
      </div>`;
  }
  return html`
    <section class="loyalty-card" aria-label="Tu tarjeta de fidelidad">
      <div class="loyalty-card__top"><span class="loyalty-card__store">${storeName}</span><span class="loyalty-card__program">${program}</span></div>
      <p class="loyalty-card__points"><span class="loyalty-card__num">${number(card.points_available)}</span> puntos disponibles</p>
      <p class="loyalty-card__rule">${card.points_pending ? `+${number(card.points_pending)} por acreditar` : `Nivel ${card.tier === 'base' ? 'inicial' : card.tier}`}</p>
      <div class="loyalty-card__bottom">
        <span><span class="sr-only">Titular: </span>${card.customer_name}<br><small>Cliente ${card.customer_id}</small></span>
        <span class="loyalty-card__code"><span class="sr-only">Número de tarjeta: </span>${card.card_number}</span>
      </div>
    </section>`;
}
