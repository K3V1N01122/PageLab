import { html, render, $, $$ } from '../utils/html.js';
import { api } from '../services/api.js';
import { cart } from '../services/cart.js';
import { store } from '../store/store.js';
import { navigate, setTitle } from '../router.js';
import { money, number, uid } from '../utils/format.js';
import { formData, showErrors, clearErrors } from '../utils/forms.js';
import { loading, empty } from '../components/states.js';
import { toast, toastError } from '../components/toast.js';
import { issuesList, readOpts, saveOpts, summary } from './cart.js';

const KEY_STORE = 'checkout:key';

/** La clave de idempotencia se conserva mientras el pedido no se confirme:
 *  si el usuario pulsa dos veces o la red falla y reintenta, se crea UN pedido. */
function idempotencyKey() {
  let k = sessionStorage.getItem(KEY_STORE);
  if (!k) { k = uid(); sessionStorage.setItem(KEY_STORE, k); }
  return k;
}

const addressFields = (a = {}) => html`
  <div class="grid-2">
    <div class="field"><label for="a-recipient">Quién recibe</label><input id="a-recipient" name="address.recipient" value="${a.recipient || ''}" autocomplete="name" required maxlength="120"></div>
    <div class="field"><label for="a-phone">Teléfono de contacto</label><input id="a-phone" name="address.phone" value="${a.phone || ''}" type="tel" autocomplete="tel" required maxlength="30"></div>
  </div>
  <div class="field"><label for="a-line1">Dirección</label><input id="a-line1" name="address.line1" value="${a.line1 || ''}" autocomplete="address-line1" required maxlength="200" placeholder="Calle, avenida, número, zona"></div>
  <div class="field"><label for="a-line2">Referencia <span class="optional">(opcional)</span></label><input id="a-line2" name="address.line2" value="${a.line2 || ''}" autocomplete="address-line2" maxlength="200"></div>
  <div class="grid-2">
    <div class="field"><label for="a-city">Municipio o ciudad</label><input id="a-city" name="address.city" value="${a.city || ''}" autocomplete="address-level2" required maxlength="100"></div>
    <div class="field"><label for="a-state">Departamento <span class="optional">(opcional)</span></label><input id="a-state" name="address.state" value="${a.state || ''}" autocomplete="address-level1" maxlength="100"></div>
  </div>`;

export default async function checkout(el) {
  setTitle('Finalizar compra');
  render(el, html`<div class="container"><h1 class="page-title">Finalizar compra</h1>${loading()}</div>`);
  const [opts, initial] = await Promise.all([api.get('/checkout/options'), cart.get()]);
  if (!initial.lines.length) {
    render(el, html`<div class="container"><h1 class="page-title">Finalizar compra</h1>
      ${empty('Tu carrito está vacío', 'Agrega productos para continuar.', { href: '/catalogo', label: 'Ver catálogo' })}</div>`);
    return;
  }
  const saved = readOpts();
  const loyalty = store.get().config.loyalty;
  const state = {
    shipping_method: saved.shipping_method || opts.shipping_methods[0]?.code,
    payment_provider: saved.payment_provider || opts.payment_providers[0]?.code,
    coupon_code: saved.coupon_code || '',
    points_to_use: 0,
    address_id: opts.addresses.find((a) => a.is_default)?.id || null,
    quote: initial,
  };
  const method = () => opts.shipping_methods.find((m) => m.code === state.shipping_method);
  const blocks = Math.floor(opts.points_available / (loyalty.redeem_block_points || 1));

  render(el, html`
    <div class="container">
      <h1 class="page-title">Finalizar compra</h1>
      <div data-slot="issues"></div>
      <form class="checkout" data-checkout novalidate>
        <div class="checkout__steps">
          <p class="form-summary notice notice--error" role="alert" tabindex="-1" hidden></p>
          <fieldset class="step">
            <legend class="step__title">Tus datos</legend>
            <div class="grid-2">
              <div class="field"><label for="c-name">Nombre completo</label><input id="c-name" name="customer.name" value="${opts.customer.name}" autocomplete="name" required maxlength="170"></div>
              <div class="field"><label for="c-phone">Teléfono</label><input id="c-phone" name="customer.phone" value="${opts.customer.phone || ''}" type="tel" autocomplete="tel" maxlength="30"></div>
            </div>
            <p class="muted">Enviaremos la confirmación a ${opts.customer.email}.</p>
          </fieldset>
          <fieldset class="step">
            <legend class="step__title">Entrega</legend>
            <div class="choices">${opts.shipping_methods.map((m) => html`
              <label class="choice"><input type="radio" name="shipping_method" value="${m.code}" ${m.code === state.shipping_method ? 'checked' : ''}>
                <span class="choice__body"><span class="choice__label">${m.label}</span><span class="choice__meta">${m.price_cents ? money(m.price_cents) : 'Gratis'}</span></span></label>`)}
            </div>
            <div data-slot="address"></div>
          </fieldset>
          <fieldset class="step">
            <legend class="step__title">Pago</legend>
            <div class="choices">${opts.payment_providers.map((p) => html`
              <label class="choice"><input type="radio" name="payment_provider" value="${p.code}" ${p.code === state.payment_provider ? 'checked' : ''}>
                <span class="choice__body"><span class="choice__label">${p.label}</span><span class="choice__meta">${p.description}</span></span></label>`)}
            </div>
          </fieldset>
          <fieldset class="step">
            <legend class="step__title">Descuentos</legend>
            <div class="grid-2">
              <div class="field"><label for="k-coupon">Cupón</label>
                <input id="k-coupon" name="coupon_code" value="${state.coupon_code}" maxlength="40" autocomplete="off"></div>
              ${loyalty.enabled ? html`<div class="field"><label for="k-points">Usar puntos <span class="optional">(tienes ${number(opts.points_available)})</span></label>
                <select id="k-points" name="points_to_use" data-type="int" ${blocks ? '' : 'disabled'}>
                  <option value="0">No usar puntos</option>
                  ${Array.from({ length: Math.min(blocks, 50) }, (_, i) => (i + 1) * loyalty.redeem_block_points).map((pts) => html`
                    <option value="${pts}">${number(pts)} puntos (−${money((pts / loyalty.redeem_block_points) * loyalty.redeem_block_value_cents)})</option>`)}
                </select></div>` : ''}
            </div>
            <button type="button" class="btn btn--secondary" data-apply>Aplicar descuentos</button>
          </fieldset>
          <div class="field"><label for="notes">Notas para la tienda <span class="optional">(opcional)</span></label>
            <textarea id="notes" name="notes" rows="3" maxlength="500"></textarea></div>
        </div>
        <aside class="checkout__summary" aria-label="Resumen del pedido">
          <h2 class="summary-title">Tu pedido</h2>
          <ul class="mini-lines" data-slot="lines"></ul>
          <div data-slot="totals" aria-live="polite"></div>
          <button type="submit" class="btn btn--primary btn--block btn--lg" data-submit>Confirmar pedido</button>
          <p class="muted small">Al confirmar aceptas los <a href="/terminos" data-link>términos y condiciones</a>.</p>
        </aside>
      </form>
    </div>`);

  const form = $('[data-checkout]', el);
  const drawAddress = () => {
    const slot = $('[data-slot="address"]', el);
    if (!method()?.requires_address) { render(slot, ''); return; }
    const sel = opts.addresses.find((a) => a.id === state.address_id);
    render(slot, html`
      ${opts.addresses.length ? html`<div class="field"><label for="addr-select">Dirección guardada</label>
        <select id="addr-select" data-address-select>
          ${opts.addresses.map((a) => html`<option value="${a.id}" ${a.id === state.address_id ? 'selected' : ''}>${a.label || a.recipient}: ${a.line1}, ${a.city}</option>`)}
          <option value="" ${!sel ? 'selected' : ''}>Usar otra dirección</option>
        </select></div>` : ''}
      ${addressFields(sel || {})}`);
    $('[data-address-select]', el)?.addEventListener('change', (e) => { state.address_id = parseInt(e.target.value, 10) || null; drawAddress(); });
  };
  const drawSummary = (q) => {
    state.quote = q;
    render($('[data-slot="issues"]', el), issuesList(q));
    render($('[data-slot="lines"]', el), q.lines.map((l) => html`
      <li><span>${l.quantity} × ${l.name}</span><span>${money(l.line_total_cents)}</span></li>`));
    const couponIssue = q.issues.find((i) => i.code === 'coupon_invalid');
    render($('[data-slot="totals"]', el), html`${couponIssue ? html`<p class="field-error">${couponIssue.message}</p>` : ''}${summary(q)}`);
    $('[data-submit]', el).disabled = !q.can_checkout;
  };
  const preview = async () => {
    try {
      const q = await cart.preview({ shipping_method: state.shipping_method, coupon_code: state.coupon_code || null, points_to_use: state.points_to_use });
      drawSummary(q);
    } catch (err) { toastError(err); }
  };

  form.addEventListener('change', (e) => {
    if (e.target.name === 'shipping_method') { state.shipping_method = e.target.value; drawAddress(); preview(); }
    if (e.target.name === 'payment_provider') state.payment_provider = e.target.value;
    saveOpts({ ...readOpts(), shipping_method: state.shipping_method, payment_provider: state.payment_provider });
  });
  $('[data-apply]', el).addEventListener('click', () => {
    state.coupon_code = form.coupon_code.value.trim().toUpperCase();
    state.points_to_use = form.points_to_use ? parseInt(form.points_to_use.value, 10) || 0 : 0;
    saveOpts({ ...readOpts(), coupon_code: state.coupon_code || null });
    preview();
  });

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    clearErrors(form);
    const btn = $('[data-submit]', el);
    if (btn.disabled) return;
    const data = formData(form);
    const body = {
      idempotency_key: idempotencyKey(),
      shipping_method: state.shipping_method,
      payment_provider: state.payment_provider,
      coupon_code: form.coupon_code.value.trim().toUpperCase() || null,
      points_to_use: form.points_to_use ? parseInt(form.points_to_use.value, 10) || 0 : 0,
      notes: data.notes,
      customer: { name: data['customer.name'], phone: data['customer.phone'] },
      expected_total_cents: state.quote.total_cents,
    };
    if (method()?.requires_address) {
      body.address = Object.fromEntries(Object.entries(data).filter(([k]) => k.startsWith('address.')).map(([k, v]) => [k.slice(8), v]));
    }
    btn.disabled = true;
    btn.textContent = 'Confirmando…';
    try {
      const order = await api.post('/checkout', body);
      sessionStorage.removeItem(KEY_STORE);
      saveOpts({});
      await cart.refreshCount();
      navigate(`/pedido/${order.order_number}`, { replace: true });
    } catch (err) {
      btn.textContent = 'Confirmar pedido';
      btn.disabled = false;
      if (err.code === 'price_changed' || err.code === 'cart_changed') {
        sessionStorage.removeItem(KEY_STORE);
        if (err.details) drawSummary(err.details);
        toast(err.message, 'error', 8000);
        $('[data-slot="issues"]', el).scrollIntoView({ behavior: 'smooth' });
      } else if (err.status === 422) {
        const details = Object.fromEntries(Object.entries(err.details || {}).map(([k, v]) => [k, v]));
        showErrors(form, { ...err, details });
        if (err.code !== 'validation_error') sessionStorage.removeItem(KEY_STORE);
      } else if (err.code === 'out_of_stock' || err.status === 409) {
        sessionStorage.removeItem(KEY_STORE);
        toastError(err);
        preview();
      } else {
        toastError(err); // error de red: se conserva la clave para reintentar sin duplicar
      }
    }
  });

  drawAddress();
  await preview();
}
