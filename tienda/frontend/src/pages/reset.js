import { html, render, $ } from '../utils/html.js';
import { auth } from '../services/auth.js';
import { setTitle } from '../router.js';
import { formData, showErrors, submitting } from '../utils/forms.js';

export default async function reset(el, ctx) {
  setTitle('Nueva contraseña');
  const token = ctx.query.get('token') || '';
  // Se quita el token de la barra de direcciones para que no quede en el historial.
  history.replaceState({}, '', '/restablecer-contrasena');
  render(el, html`
    <div class="container auth"><div class="auth__panel">
      <h1 class="page-title">Crea una contraseña nueva</h1>
      ${token ? html`
      <form data-reset novalidate>
        <p class="form-summary notice notice--error" role="alert" tabindex="-1" hidden></p>
        <div class="field"><label for="password">Contraseña nueva</label><input id="password" name="password" type="password" autocomplete="new-password" required></div>
        <div class="field"><label for="password_confirm">Confirmar contraseña</label><input id="password_confirm" name="password_confirm" type="password" autocomplete="new-password" required></div>
        <button class="btn btn--primary btn--block" type="submit">Guardar contraseña</button>
      </form>` : html`<p class="notice notice--error">El enlace no es válido. <a href="/recuperar-contrasena" data-link>Solicita uno nuevo</a>.</p>`}
    </div></div>`);
  const form = $('[data-reset]', el);
  form?.addEventListener('submit', (e) => {
    e.preventDefault();
    submitting(form, async () => {
      try {
        const r = await auth.reset({ ...formData(form), token });
        render(form, html`<div class="notice notice--success" role="status"><p>${r.message}</p><p><a class="btn btn--primary" href="/iniciar-sesion" data-link>Iniciar sesión</a></p></div>`);
      } catch (err) { showErrors(form, err); }
    });
  });
}
