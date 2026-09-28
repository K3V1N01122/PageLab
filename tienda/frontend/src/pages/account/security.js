import { html, render, $ } from '../../utils/html.js';
import { auth } from '../../services/auth.js';
import { setTitle } from '../../router.js';
import { formData, showErrors, submitting } from '../../utils/forms.js';
import { toast } from '../../components/toast.js';
import { accountLayout, bindLayout } from './layout.js';

export default async function security(el) {
  setTitle('Seguridad');
  render(el, accountLayout('/cuenta/seguridad', 'Seguridad', html`
    <form class="form-card" data-password novalidate>
      <h2 class="section__title">Cambiar contraseña</h2>
      <p class="form-summary notice notice--error" role="alert" tabindex="-1" hidden></p>
      <div class="field"><label for="current_password">Contraseña actual</label><input id="current_password" name="current_password" type="password" autocomplete="current-password" required></div>
      <div class="grid-2">
        <div class="field"><label for="password">Contraseña nueva</label><input id="password" name="password" type="password" autocomplete="new-password" required></div>
        <div class="field"><label for="password_confirm">Confirmar contraseña</label><input id="password_confirm" name="password_confirm" type="password" autocomplete="new-password" required></div>
      </div>
      <p class="help">Al cambiarla cerraremos tu sesión en otros dispositivos.</p>
      <button class="btn btn--primary" type="submit">Cambiar contraseña</button>
    </form>`));
  bindLayout(el);
  const form = $('[data-password]', el);
  form.addEventListener('submit', (e) => {
    e.preventDefault();
    submitting(form, async () => {
      try { const r = await auth.changePassword(formData(form)); form.reset(); toast(r.message); } catch (err) { showErrors(form, err); }
    });
  });
}
