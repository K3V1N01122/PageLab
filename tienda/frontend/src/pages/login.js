import { html, render, $ } from '../utils/html.js';
import { auth } from '../services/auth.js';
import { navigate, setTitle } from '../router.js';
import { formData, showErrors, submitting } from '../utils/forms.js';

/** Solo se permite redirigir a rutas internas (evita open redirect). */
export const safeNext = (q, fallback = '/cuenta') => {
  const n = q.get('next') || '';
  return n.startsWith('/') && !n.startsWith('//') ? n : fallback;
};

export default async function login(el, ctx) {
  setTitle('Iniciar sesión');
  render(el, html`
    <div class="container auth">
      <div class="auth__panel">
        <h1 class="page-title">Iniciar sesión</h1>
        <form data-login novalidate>
          <p class="form-summary notice notice--error" role="alert" tabindex="-1" hidden></p>
          <div class="field"><label for="email">Correo electrónico</label>
            <input id="email" name="email" type="email" autocomplete="email" required maxlength="254"></div>
          <div class="field"><label for="password">Contraseña</label>
            <input id="password" name="password" type="password" autocomplete="current-password" required maxlength="128"></div>
          <div class="auth__row">
            <label class="check"><input type="checkbox" name="remember"> Mantener la sesión iniciada</label>
            <a href="/recuperar-contrasena" data-link>¿Olvidaste tu contraseña?</a>
          </div>
          <button class="btn btn--primary btn--block btn--lg" type="submit">Iniciar sesión</button>
        </form>
        <p class="auth__alt">¿No tienes cuenta? <a href="/registro${ctx.query.get('next') ? `?next=${encodeURIComponent(ctx.query.get('next'))}` : ''}" data-link>Crear cuenta</a></p>
      </div>
    </div>`);
  const form = $('[data-login]', el);
  form.addEventListener('submit', (e) => {
    e.preventDefault();
    submitting(form, async () => {
      try {
        await auth.login(formData(form));
        navigate(safeNext(ctx.query), { replace: true });
      } catch (err) {
        showErrors(form, err);
      }
    });
  });
}
