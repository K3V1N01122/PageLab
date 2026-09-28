import { $$ } from './html.js';

/** Lee un formulario como objeto. Checkboxes -> boolean, data-type="int" -> número. */
export function formData(form) {
  const out = {};
  for (const el of form.elements) {
    if (!el.name || el.disabled) continue;
    if (el.type === 'checkbox') out[el.name] = el.checked;
    else if (el.type === 'radio') { if (el.checked) out[el.name] = el.value; }
    else if (el.dataset.type === 'int') out[el.name] = el.value === '' ? null : parseInt(el.value, 10);
    else if (el.dataset.type === 'money') out[el.name] = el.value === '' ? null : Math.round(parseFloat(el.value) * 100);
    else out[el.name] = el.value;
  }
  return out;
}

/** Muestra errores de validación del backend junto a cada campo (accesible). */
export function showErrors(form, error) {
  clearErrors(form);
  const details = error?.details || {};
  let first = null;
  for (const [field, msg] of Object.entries(details)) {
    const input = form.querySelector(`[name="${CSS.escape(field)}"]`);
    if (!input) continue;
    const id = `${input.id || input.name}-error`;
    const p = document.createElement('p');
    p.className = 'field-error';
    p.id = id;
    p.textContent = msg;
    input.setAttribute('aria-invalid', 'true');
    input.setAttribute('aria-describedby', id);
    (input.closest('.field') || input.parentElement).appendChild(p);
    first = first || input;
  }
  const summary = form.querySelector('.form-summary');
  if (summary) {
    summary.textContent = error?.message || 'Revisa los campos marcados.';
    summary.hidden = false;
  }
  (first || summary)?.focus?.();
}

export function clearErrors(form) {
  $$('.field-error', form).forEach((e) => e.remove());
  $$('[aria-invalid]', form).forEach((e) => { e.removeAttribute('aria-invalid'); e.removeAttribute('aria-describedby'); });
  const summary = form.querySelector('.form-summary');
  if (summary) summary.hidden = true;
}

/** Deshabilita el botón mientras se envía (evita dobles envíos). */
export async function submitting(form, fn) {
  const btn = form.querySelector('[type="submit"]');
  if (btn?.disabled) return;
  const label = btn?.textContent;
  if (btn) { btn.disabled = true; btn.setAttribute('aria-busy', 'true'); }
  try { return await fn(); } finally {
    if (btn) { btn.disabled = false; btn.removeAttribute('aria-busy'); btn.textContent = label; }
  }
}
