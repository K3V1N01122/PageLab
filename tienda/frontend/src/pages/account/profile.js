import { html, render, $ } from '../../utils/html.js';
import { api } from '../../services/api.js';
import { store } from '../../store/store.js';
import { setTitle } from '../../router.js';
import { formData, showErrors, submitting } from '../../utils/forms.js';
import { toast } from '../../components/toast.js';
import { accountLayout, bindLayout } from './layout.js';

export default async function profile(el) {
  setTitle('Datos personales');
  const { user } = await api.get('/account/profile');
  render(el, accountLayout('/cuenta/perfil', 'Datos personales', html`
    <form class="form-card" data-profile novalidate>
      <p class="form-summary notice notice--error" role="alert" tabindex="-1" hidden></p>
      <div class="grid-2">
        <div class="field"><label for="first_name">Nombre</label><input id="first_name" name="first_name" value="${user.first_name}" required maxlength="80" autocomplete="given-name"></div>
        <div class="field"><label for="last_name">Apellido</label><input id="last_name" name="last_name" value="${user.last_name}" required maxlength="80" autocomplete="family-name"></div>
      </div>
      <div class="field"><label for="email">Correo electrónico</label><input id="email" value="${user.email}" disabled aria-describedby="email-help">
        <p class="help" id="email-help">Para cambiar tu correo, contacta a la tienda.</p></div>
      <div class="field"><label for="phone">Teléfono</label><input id="phone" name="phone" type="tel" value="${user.phone || ''}" maxlength="30" autocomplete="tel"></div>
      <p class="muted">Identificador de cliente: ${user.id}</p>
      <button class="btn btn--primary" type="submit">Guardar cambios</button>
    </form>`));
  bindLayout(el);
  const form = $('[data-profile]', el);
  form.addEventListener('submit', (e) => {
    e.preventDefault();
    submitting(form, async () => {
      try {
        const r = await api.put('/account/profile', formData(form));
        store.set({ user: { ...store.get().user, ...r.user } });
        toast('Datos guardados.');
      } catch (err) { showErrors(form, err); }
    });
  });
}
