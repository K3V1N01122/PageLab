import { html, render, $, $$ } from '../utils/html.js';
import { cart } from '../services/cart.js';
import { store } from '../store/store.js';
import { navigate, setTitle } from '../router.js';
import { money, number } from '../utils/format.js';
import { icons } from '../components/icons.js';
import { empty, errorState, loading } from '../components/states.js';
import { toast, toastError } from '../components/toast.js';

const OPTS_KEY = 'checkout:opts';
export const readOpts = () => { try { return JSON.parse(sessionStorage.getItem(OPTS_KEY) || '{}'); } catch { return {}; } };
export const saveOpts = (o) => { try { sessionStorage.setItem(OPTS_KEY, JSON.stringify(o)); } catch { /* noop */ } };

export function summary(q, { showPoints = true } = {}) {
  return html`
    <dl class="totals">
      <div><dt>Subtotal (${number(q.item_count)} ${q.item_count === 1 ? 'producto' : 'productos'})</dt><dd>${money(q.subtotal_cents)}</dd></div>
      ${q.discount_cents ? html`<div class="totals__discount"><dt>Descuento${q.coupon ? ` (${q.coupon.code})` : ''}</dt><dd>−${money(q.discount_cents)}</dd></div>` : ''}
      ${q.coupon && q.coupon.kind === 'free_shipping' ? html`<div class="totals__discount"><dt>Cupón ${q.coupon.code}</dt><dd>Envío gratis</dd></div>` : ''}
      ${showPoints && q.points_used ? html`<div class="totals__discount"><dt>Puntos (${number(q.points_used)})</dt><dd>−${money(q.points_discount_cents)}</dd></div>` : ''}
      <div><dt>Envío</dt><dd>${q.shipping_method ? (q.shipping_cents ? money(q.shipping_cents) : 'Gratis') : 'Se calcula en el checkout'}</dd></div>
      <div class="totals__total"><dt>Total</dt><dd>${money(q.total_cents)}</dd></div>
      ${q.points_earned ? html`<div class="totals__earn"><dt>Sumarás</dt><dd>${number(q.points_earned)} puntos</dd></div>` : ''}
    </dl>`;
}

export function issuesList(q) {
  const list = q.issues.filter((i) => i.code !== 'coupon_invalid');
  if (!list.length && !q.price_changes?.length) return '';
  return html`<div class="notice notice--warn" role="alert">
    <ul>
      ${q.price_changes?.length ? html`<li>Algunos precios cambiaron desde que agregaste los productos. El carrito ya muestra los precios actuales.</li>` : ''}
      ${list.map((i) => html`<li>${i.message}</li>`)}
    </ul></div>`;
}

export default async function cartPage(el) {
  setTitle('Carrito');
  const user = store.get().user;
  const opts = readOpts();
  render(el, html`<div class="container"><h1 class="page-title">Carrito</h1>${loading()}</div>`);

  const draw = (q) => {
    if (!q.lines.length && !q.issues.length) {
      render(el, html`<div class="container"><h1 class="page-title">Carrito</h1>
        ${empty('Tu carrito está vacío', 'Explora el catálogo y agrega lo que te guste.', { href: '/catalogo', label: 'Ver catálogo' })}</div>`);
      return;
    }
    const couponIssue = q.issues.find((i) => i.code === 'coupon_invalid');
    render(el, html`
      <div class="container">
        <h1 class="page-title">Carrito</h1>
        ${issuesList(q)}
        <div class="cart">
          <ul class="cart__lines" aria-label="Productos en el carrito">
            ${q.lines.map((l) => html`
            <li class="cart-line" data-id="${l.product_id}">
              <a href="/producto/${l.slug}" data-link class="cart-line__img" tabindex="-1" aria-hidden="true">
                ${l.image_url ? html`<img src="${l.image_url}" alt="" width="96" height="96" loading="lazy">` : ''}</a>
              <div class="cart-line__info">
                <a href="/producto/${l.slug}" data-link class="cart-line__name">${l.name}</a>
                <p class="cart-line__unit">${money(l.unit_price_cents)} c/u
                  ${l.previous_unit_price_cents ? html`<span class="cart-line__changed">(antes ${money(l.previous_unit_price_cents)})</span>` : ''}</p>
                ${l.quantity > l.stock ? html`<p class="field-error">Solo quedan ${l.stock}.</p>` : ''}
              </div>
              <div class="qty__control qty__control--sm">
                <button type="button" class="icon-btn" data-qty="${l.quantity - 1}" aria-label="Disminuir cantidad de ${l.name}" ${l.quantity <= 1 ? 'disabled' : ''}>${icons.minus}</button>
                <span class="qty__value" aria-label="Cantidad">${l.quantity}</span>
                <button type="button" class="icon-btn" data-qty="${l.quantity + 1}" aria-label="Aumentar cantidad de ${l.name}" ${l.quantity >= l.stock ? 'disabled' : ''}>${icons.plus}</button>
              </div>
              <p class="cart-line__total">${money(l.line_total_cents)}</p>
              <button type="button" class="icon-btn cart-line__remove" data-remove aria-label="Quitar ${l.name} del carrito">${icons.trash}</button>
            </li>`)}
            ${q.issues.filter((i) => i.product_id && !q.lines.some((l) => l.product_id === i.product_id)).map((i) => html`
            <li class="cart-line cart-line--gone" data-id="${i.product_id}"><p>${i.message}</p>
              <button type="button" class="btn btn--ghost" data-remove>Quitar</button></li>`)}
          </ul>
          <aside class="cart__summary" aria-label="Resumen">
            <h2 class="summary-title">Resumen</h2>
            ${user ? html`
              <form class="inline-form" data-coupon>
                <label for="coupon">Cupón de descuento</label>
                <div class="inline-form__row"><input id="coupon" name="coupon" value="${opts.coupon_code || ''}" maxlength="40" autocomplete="off" ${couponIssue ? html`aria-invalid="true" aria-describedby="coupon-err"` : ''}>
                  <button class="btn btn--secondary" type="submit">Aplicar</button></div>
                ${couponIssue ? html`<p class="field-error" id="coupon-err">${couponIssue.message}</p>` : ''}
              </form>
              ${store.get().config.loyalty.enabled ? html`<p class="muted">Podrás usar tus puntos en el siguiente paso.</p>` : ''}`
            : html`<p class="muted"><a href="/iniciar-sesion?next=/carrito" data-link>Inicia sesión</a> para usar cupones y puntos.</p>`}
            ${summary(q)}
            <a class="btn btn--primary btn--block btn--lg ${q.can_checkout ? '' : 'is-disabled'}" href="/checkout" data-link
              ${q.can_checkout ? '' : html`aria-disabled="true"`}>Continuar con la compra</a>
            <a class="btn btn--ghost btn--block" href="/catalogo" data-link>Seguir comprando</a>
          </aside>
        </div>
      </div>`);
    bind();
  };

  const refresh = async () => {
    const o = readOpts();
    const q = user && o.coupon_code ? await cart.preview({ coupon_code: o.coupon_code }) : await cart.get();
    draw(q);
  };

  const bind = () => {
    $$('[data-qty]', el).forEach((b) => b.addEventListener('click', async () => {
      const id = parseInt(b.closest('[data-id]').dataset.id, 10);
      b.disabled = true;
      try { await cart.setQty(id, parseInt(b.dataset.qty, 10)); await refresh(); } catch (err) { toastError(err); b.disabled = false; }
    }));
    $$('[data-remove]', el).forEach((b) => b.addEventListener('click', async () => {
      const id = parseInt(b.closest('[data-id]').dataset.id, 10);
      try { await cart.remove(id); await refresh(); toast('Producto quitado del carrito.'); } catch (err) { toastError(err); }
    }));
    $('[data-coupon]', el)?.addEventListener('submit', async (e) => {
      e.preventDefault();
      const code = e.target.coupon.value.trim().toUpperCase();
      saveOpts({ ...readOpts(), coupon_code: code || null });
      await refresh();
      const applied = $('#coupon-err', el) ? null : code;
      if (applied) toast('Cupón aplicado.');
    });
    $('.is-disabled', el)?.addEventListener('click', (e) => { e.preventDefault(); toast('Revisa los avisos del carrito antes de continuar.', 'error'); });
  };

  try { await refresh(); } catch (err) {
    render(el, html`<div class="container"><h1 class="page-title">Carrito</h1>${errorState(err)}</div>`);
    $('[data-action="retry"]', el)?.addEventListener('click', () => navigate('/carrito', { replace: true }));
  }
}
