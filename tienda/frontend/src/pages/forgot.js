import { html, render, $ } from '../utils/html.js';
import { auth } from '../services/auth.js';
import { setTitle } from '../router.js';
import { formData, showErrors, submitting } from '../utils/forms.js';

export default async function forgot(el) {
  setTitle('Recuperar contraseña');
  render(el, html`
    <div class="container auth"><div class="auth__panel">
      <h1 class="page-title">Recuperar contraseña</h1>
      <p class="page-lead">Te enviaremos un enlace para crear una contraseña nueva.</p>
      <form data-forgot novalidate>
        <p class="form-summary notice notice--error" role="alert" tabindex="-1" hidden></p>
        <div class="field"><label for="email">Correo electrónico</label><input id="email" name="email" type="email" autocomplete="email" required></div>
        <button class="btn btn--primary btn--block" type="submit">Enviar enlace</button>
      </form>
      <p class="auth__alt"><a href="/iniciar-sesion" data-link>Volver a iniciar sesión</a></p>
    </div></div>`);
  const form = $('[data-forgot]', el);
  form.addEventListener('submit', (e) => {
    e.preventDefault();
    submitting(form, async () => {
      try {
        const r = await auth.forgot(formData(form).email);
        render(form, html`<div class="notice notice--success" role="status"><p>${r.message}</p></div>`);
      } catch (err) { showErrors(form, err); }
    });
  });
}
