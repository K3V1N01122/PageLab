/**
 * Movimiento de la interfaz (sin librerías).
 *
 * - [data-reveal]: el elemento aparece al entrar en pantalla (sube y se desvanece).
 * - [data-reveal="stagger"]: sus hijos aparecen uno tras otro.
 * - [data-split]: el texto se parte en palabras que suben desde una máscara.
 *
 * Todo respeta la preferencia del sistema «reducir movimiento»: en ese caso
 * los elementos se muestran de inmediato, sin animación.
 */
const reduced = () => window.matchMedia('(prefers-reduced-motion: reduce)').matches;
let io;

function show(el) {
  // Los hijos pueden haber llegado después (contenido cargado desde la API).
  if (el.dataset.reveal === 'stagger') [...el.children].forEach((c, i) => c.style.setProperty('--i', Math.min(i, 12)));
  el.classList.add('is-in');
  io?.unobserve(el);
}

function prepare(el) {
  if (el.dataset.motionReady) return;
  el.dataset.motionReady = '1';
  if (el.hasAttribute('data-split')) splitWords(el);
  if (reduced() || !io) show(el);
  else io.observe(el);
}

/** Parte el texto en palabras con máscara, conservando el texto accesible. */
export function splitWords(el) {
  const text = el.textContent.trim();
  el.textContent = '';
  const sr = document.createElement('span');
  sr.className = 'sr-only';
  sr.textContent = text;       // texto completo para lectores de pantalla
  el.appendChild(sr);
  text.split(/\s+/).forEach((word, i) => {
    const outer = document.createElement('span');
    outer.className = 'split-w';
    outer.setAttribute('aria-hidden', 'true');
    const inner = document.createElement('span');
    inner.textContent = word;
    inner.style.setProperty('--i', i);
    outer.appendChild(inner);
    el.appendChild(outer);
    el.appendChild(document.createTextNode(' '));
  });
}

function scan(root) {
  if (root.nodeType !== 1) return;
  if (root.matches('[data-reveal], [data-split]')) prepare(root);
  root.querySelectorAll('[data-reveal], [data-split]').forEach(prepare);
}

/** Se llama una vez al arrancar: detecta elementos nuevos en cualquier página. */
export function initMotion() {
  document.documentElement.classList.add('motion-ready');
  if ('IntersectionObserver' in window) {
    io = new IntersectionObserver((entries) => {
      entries.forEach((e) => { if (e.isIntersecting) show(e.target); });
    }, { rootMargin: '0px 0px -8% 0px', threshold: 0.12 });
  }
  scan(document.body);
  new MutationObserver((muts) => muts.forEach((m) => m.addedNodes.forEach(scan)))
    .observe(document.body, { childList: true, subtree: true });
}

/** Convierte «texto con *palabras* resaltadas» en partes seguras para html``. */
export function emphasis(text, wrap) {
  return String(text || '').split(/\*([^*]+)\*/).map((part, i) => (i % 2 ? wrap(part) : part));
}
