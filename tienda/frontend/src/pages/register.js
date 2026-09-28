import { html, render, $ } from '../utils/html.js';
import { auth } from '../services/auth.js';
import { store } from '../store/store.js';
import { navigate, setTitle } from '../router.js';
import { formData, showErrors, submitting } from '../utils/forms.js';
import { toast } from '../components/toast.js';
import { safeNext } from './login.js';

export default async function register(el, ctx) {
  setTitle('Crear cuenta');
  const loyalty = store.get().config.loyalty;
  render(el, html`
    <div class="container auth">
      <div class="auth__panel">
        <h1 class="page-title">Crear cuenta</h1>
        ${loyalty.enabled ? html`<p class="page-lead">Al registrarte recibes tu tarjeta virtual de ${loyalty.program_name.toLowerCase()} y empiezas a sumar desde tu primera compra.</p>` : ''}
        <form data-register novalidate>
          <p class="form-summary notice notice--error" role="alert" tabindex="-1" hidden></p>
          <div class="grid-2">
            <div class="field"><label for="first_name">Nombre</label><input id="first_name" name="first_name" autocomplete="given-name" required maxlength="80"></div>
            <div class="field"><label for="last_name">Apellido</label><input id="last_name" name="last_name" autocomplete="family-name" required maxlength="80"></div>
          </div>
          <div class="field"><label for="email">Correo electrónico</label><input id="email" name="email" type="email" autocomplete="email" required maxlength="254"></div>
          <div class="field"><label for="phone">Teléfono <span class="optional">(opcional)</span></label><input id="phone" name="phone" type="tel" autocomplete="tel" maxlength="30"></div>
          <div class="grid-2">
            <div class="field"><label for="password">Contraseña</label>
              <input id="password" name="password" type="password" autocomplete="new-password" required minlength="8" maxlength="128" aria-describedby="pw-help">
              <p class="help" id="pw-help">Mínimo 8 caracteres, con letras y números.</p></div>
            <div class="field"><label for="password_confirm">Confirmar contraseña</label>
              <input id="password_confirm" name="password_confirm" type="password" autocomplete="new-password" required maxlength="128"></div>
          </div>
          <div class="field"><label class="check"><input type="checkbox" name="accept_terms" required>
            Acepto los <a href="/terminos" target="_blank" rel="noopener">términos y condiciones</a> y la <a href="/privacidad" target="_blank" rel="noopener">política de privacidad</a></label></div>
          <button class="btn btn--primary btn--block btn--lg" type="submit">Crear cuenta</button>
        </form>
        <p class="auth__alt">¿Ya tienes cuenta? <a href="/iniciar-sesion" data-link>Iniciar sesión</a></p>
      </div>
    </div>`);
  const form = $('[data-register]', el);
  form.addEventListener('submit', (e) => {
    e.preventDefault();
    const data = formData(form);
    if (data.password !== data.password_confirm) {
      showErrors(form, { message: 'Revisa los campos marcados.', details: { password_confirm: 'Las contraseñas no coinciden.' } });
      return;
    }
    submitting(form, async () => {
      try {
        await auth.register(data);
        toast('Tu cuenta está lista.');
        navigate(safeNext(ctx.query), { replace: true });
      } catch (err) { showErrors(form, err); }
    });
  });
}
