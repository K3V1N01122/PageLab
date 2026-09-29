import { html, render, $$ } from '../../utils/html.js';
import { api } from '../../services/api.js';
import { formData, showErrors } from '../../utils/forms.js';
import { toast } from '../../components/toast.js';
import { checkbox, input, moneyInput, pageHead, select, textarea } from '../ui.js';
import { DEFAULT_FONT, FONT_PRESETS } from '../../utils/fonts.js';

/** Configuración central: un solo lugar para nombre, colores, contacto, redes, envíos y SEO. */
export default async function settings(el) {
  const s = await api.get('/admin/settings');
  const methods = s.shipping.methods || [];
  render(el, html`
    ${pageHead('Configuración')}
    <p class="help">Estos datos se usan en toda la tienda. Un cambio puede tardar hasta un minuto en verse.</p>
    <div class="a-grid">
      <form class="a-card" data-key="store" novalidate><h2 class="a-card__title">Tienda</h2>
        <p class="form-summary notice notice--error" role="alert" tabindex="-1" hidden></p>
        ${input('name', 'Nombre de la tienda', s.store.name, { required: true })}
        ${input('tagline', 'Frase descriptiva', s.store.tagline, { attrs: 'maxlength="160"' })}
        ${textarea('statement', 'Mensaje de la marca (portada)', s.store.statement, 3)}
        <p class="help">Escribe entre *asteriscos* las palabras que quieras resaltar. Ej.: Hecho para *durar*, pensado para *ti*.</p>
        ${input('closing_line', 'Frase de cierre (pie de página)', s.store.closing_line, { optional: true, attrs: 'maxlength="60"', help: 'Se muestra en letras gigantes al final de cada página. Si la dejas vacía, se usa el nombre de la tienda.' })}
        ${input('logo_url', 'URL del logo', s.store.logo_url, { optional: true, help: 'Sube la imagen desde Productos > Subir imagen y pega aquí su URL (/uploads/...).' })}
        <button class="btn btn--primary" type="submit">Guardar</button></form>
      <form class="a-card" data-key="theme" novalidate><h2 class="a-card__title">Colores y tipografía</h2>
        <p class="form-summary notice notice--error" role="alert" tabindex="-1" hidden></p>
        ${select('font', 'Tipografía', Object.entries(FONT_PRESETS).map(([k, p]) => [k, p.label]), s.theme.font || DEFAULT_FONT)}
        <p class="help">Cambia la letra de los títulos y los textos de toda la tienda. Recarga la tienda con Ctrl + F5 para verla.</p>
        ${input('primary', 'Color principal (texto y encabezados)', s.theme.primary, { type: 'color' })}
        ${input('accent', 'Color de acciones (botones)', s.theme.accent, { type: 'color' })}
        ${input('points', 'Color del programa de puntos', s.theme.points, { type: 'color' })}
        <p class="help">Verifica el contraste: el texto blanco debe leerse bien sobre el color de acciones.</p>
        <button class="btn btn--primary" type="submit">Guardar</button></form>
      <form class="a-card" data-key="contact" novalidate><h2 class="a-card__title">Contacto</h2>
        <p class="form-summary notice notice--error" role="alert" tabindex="-1" hidden></p>
        ${input('whatsapp', 'WhatsApp', s.contact.whatsapp, { optional: true, help: 'Con código de país, p. ej. +502 5555 5555.' })}
        ${input('phone', 'Teléfono', s.contact.phone, { optional: true })}
        ${input('email', 'Correo', s.contact.email, { type: 'email', optional: true })}
        ${input('address', 'Dirección', s.contact.address, { optional: true })}
        ${input('hours', 'Horario', s.contact.hours, { optional: true })}
        <button class="btn btn--primary" type="submit">Guardar</button></form>
      <form class="a-card" data-key="social" novalidate><h2 class="a-card__title">Redes sociales</h2>
        <p class="form-summary notice notice--error" role="alert" tabindex="-1" hidden></p>
        ${input('instagram', 'Instagram (URL)', s.social.instagram, { type: 'url', optional: true })}
        ${input('facebook', 'Facebook (URL)', s.social.facebook, { type: 'url', optional: true })}
        ${input('tiktok', 'TikTok (URL)', s.social.tiktok, { type: 'url', optional: true })}
        <button class="btn btn--primary" type="submit">Guardar</button></form>
      <form class="a-card" data-key="shipping" novalidate><h2 class="a-card__title">Métodos de entrega</h2>
        <p class="form-summary notice notice--error" role="alert" tabindex="-1" hidden></p>
        ${methods.map((m, i) => html`<fieldset class="a-fieldset"><legend>${m.label}</legend>
          ${input(`m${i}_label`, 'Nombre', m.label)}
          ${moneyInput(`m${i}_price_cents`, 'Costo (Q)', m.price_cents)}
          ${checkbox(`m${i}_requires_address`, 'Pide dirección', m.requires_address)}
          ${checkbox(`m${i}_active`, 'Disponible', m.active !== false)}</fieldset>`)}
        ${moneyInput('free_shipping_over_cents', 'Envío gratis desde (Q)', s.shipping.free_shipping_over_cents, { optional: true, help: 'Vacío = sin envío gratis automático.' })}
        <p class="help">La empresa de envíos aún no está definida; estos costos son configurables.</p>
        <button class="btn btn--primary" type="submit">Guardar</button></form>
      <form class="a-card" data-key="payments" novalidate><h2 class="a-card__title">Pagos</h2>
        <p class="form-summary notice notice--error" role="alert" tabindex="-1" hidden></p>
        ${textarea('bank_transfer_instructions', 'Instrucciones para transferencia', s.payments.bank_transfer_instructions, 3, false)}
        <p class="help">Los proveedores habilitados se configuran en el servidor (variable PAYMENT_PROVIDERS), nunca desde el navegador.</p>
        <button class="btn btn--primary" type="submit">Guardar</button></form>
      <form class="a-card" data-key="notifications" novalidate><h2 class="a-card__title">Avisos de pedidos</h2>
        <p class="form-summary notice notice--error" role="alert" tabindex="-1" hidden></p>
        ${input('new_order_emails', 'Correos que reciben cada pedido nuevo', (s.notifications || {}).new_order_emails, { optional: true, help: 'Hasta 5, separados por comas. Ej.: ventas@gmail.com, dueño@gmail.com' })}
        <button class="btn btn--primary" type="submit">Guardar</button></form>
      <form class="a-card" data-test-email novalidate><h2 class="a-card__title">Probar el correo</h2>
        <p class="form-summary notice notice--error" role="alert" tabindex="-1" hidden></p>
        <p class="help">Envía un correo de prueba para confirmar que la tienda puede mandar confirmaciones. La cuenta de envío se configura en el archivo .env del servidor (SMTP_USER y SMTP_PASSWORD).</p>
        ${input('to', 'Enviar a', '', { type: 'email' })}
        <button class="btn btn--secondary" type="submit">Enviar correo de prueba</button></form>
      <form class="a-card" data-key="seo" novalidate><h2 class="a-card__title">SEO</h2>
        <p class="form-summary notice notice--error" role="alert" tabindex="-1" hidden></p>
        ${input('default_title', 'Título de la página de inicio', s.seo.default_title, { attrs: 'maxlength="70"' })}
        ${input('default_description', 'Descripción para buscadores', s.seo.default_description, { attrs: 'maxlength="170"' })}
        ${input('og_image', 'Imagen para redes sociales (URL)', s.seo.og_image, { optional: true })}
        <button class="btn btn--primary" type="submit">Guardar</button></form>
    </div>`);
  $$('form[data-test-email]', el).forEach((f) => f.addEventListener('submit', async (e) => {
    e.preventDefault();
    const btn = f.querySelector('button');
    btn.disabled = true;
    try { const r = await api.post('/admin/settings/test-email', { to: f.to.value }); toast(r.message); }
    catch (err) { showErrors(f, err); } finally { btn.disabled = false; }
  }));
  $$('form[data-key]', el).forEach((f) => f.addEventListener('submit', async (e) => {
    e.preventDefault();
    const key = f.dataset.key;
    let body = formData(f);
    Object.keys(body).forEach((k) => { if (body[k] === '') body[k] = null; });
    if (key === 'shipping') {
      body = {
        free_shipping_over_cents: body.free_shipping_over_cents,
        methods: methods.map((m, i) => ({ ...m, label: body[`m${i}_label`] || m.label, price_cents: body[`m${i}_price_cents`] ?? 0,
          requires_address: body[`m${i}_requires_address`], active: body[`m${i}_active`] })),
      };
    }
    try { await api.put(`/admin/settings/${key}`, body); toast('Configuración guardada.'); } catch (err) { showErrors(f, err); }
  }));
}
