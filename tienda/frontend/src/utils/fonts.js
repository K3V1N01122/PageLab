/**
 * Combinaciones tipográficas (títulos + textos) seleccionables desde
 * Panel > Configuración > Colores y tipografía. Todas son de Google Fonts,
 * gratuitas para uso comercial. Para agregar una nueva, copia un bloque.
 *
 * display: familia para titulares grandes · body: familia para textos
 * weight/tracking/leading/transform: cómo se comporta el titular.
 */
export const FONT_PRESETS = {
  deportiva: {
    label: 'Deportiva (condensada, con energía)',
    url: 'https://fonts.googleapis.com/css2?family=Big+Shoulders:wght@700;800;900&family=Archivo:wght@400;500;600;700;800&display=swap',
    display: '"Big Shoulders", "Archivo Narrow", "Arial Narrow", sans-serif',
    body: '"Archivo", ui-sans-serif, system-ui, sans-serif',
    weight: 900, tracking: '-0.01em', leading: 0.88, transform: 'uppercase', scale: 1.18,
  },
  editorial: {
    label: 'Editorial (elegante, moda y lujo)',
    url: 'https://fonts.googleapis.com/css2?family=Bodoni+Moda:opsz,wght@6..96,500;6..96,700;6..96,800&family=Albert+Sans:wght@400;500;600;700&display=swap',
    display: '"Bodoni Moda", "Didot", Georgia, serif',
    body: '"Albert Sans", ui-sans-serif, system-ui, sans-serif',
    weight: 700, tracking: '-0.035em', leading: 0.92, transform: 'none', scale: 1,
  },
  urbana: {
    label: 'Urbana (impacto, streetwear)',
    url: 'https://fonts.googleapis.com/css2?family=Anton&family=Barlow:wght@400;500;600;700&display=swap',
    display: '"Anton", "Impact", "Arial Narrow", sans-serif',
    body: '"Barlow", ui-sans-serif, system-ui, sans-serif',
    weight: 400, tracking: '0em', leading: 0.9, transform: 'uppercase', scale: 1.05,
  },
  clasica: {
    label: 'Clásica (grotesca sobria)',
    url: 'https://fonts.googleapis.com/css2?family=Schibsted+Grotesk:wght@400;500;600;700;800&display=swap',
    display: '"Schibsted Grotesk", ui-sans-serif, system-ui, sans-serif',
    body: '"Schibsted Grotesk", ui-sans-serif, system-ui, sans-serif',
    weight: 800, tracking: '-0.055em', leading: 0.86, transform: 'none', scale: 1,
  },
};

export const DEFAULT_FONT = 'deportiva';

export function applyFont(key) {
  const p = FONT_PRESETS[key] || FONT_PRESETS[DEFAULT_FONT];
  let link = document.getElementById('font-preset');
  if (!link) {
    link = document.createElement('link');
    link.id = 'font-preset';
    link.rel = 'stylesheet';
    document.head.appendChild(link);
  }
  if (link.href !== p.url) link.href = p.url;
  const r = document.documentElement.style;
  r.setProperty('--font', p.body);
  r.setProperty('--font-display', p.display);
  r.setProperty('--display-weight', p.weight);
  r.setProperty('--display-tracking', p.tracking);
  r.setProperty('--display-leading', p.leading);
  r.setProperty('--display-transform', p.transform);
  r.setProperty('--display-scale', p.scale);
}
