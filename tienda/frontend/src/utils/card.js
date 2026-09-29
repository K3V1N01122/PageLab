/**
 * Utilidades de tarjeta (solo en el navegador).
 * El número completo y el CVV se validan aquí y NUNCA se envían al servidor.
 */
export function digits(v) { return String(v || '').replace(/\D/g, ''); }

export function detectBrand(num) {
  const n = digits(num);
  if (/^4/.test(n)) return 'visa';
  const two = parseInt(n.slice(0, 2), 10);
  const four = parseInt(n.slice(0, 4), 10);
  if ((two >= 51 && two <= 55) || (four >= 2221 && four <= 2720)) return 'mastercard';
  return null;
}

export const BRAND_LABEL = { visa: 'Visa', mastercard: 'Mastercard' };

/** Algoritmo de Luhn: detecta números mal escritos. */
export function luhn(num) {
  const n = digits(num);
  let sum = 0;
  for (let i = 0; i < n.length; i++) {
    let d = parseInt(n[n.length - 1 - i], 10);
    if (i % 2 === 1) { d *= 2; if (d > 9) d -= 9; }
    sum += d;
  }
  return n.length > 0 && sum % 10 === 0;
}

export function formatNumber(v) { return digits(v).slice(0, 19).replace(/(\d{4})(?=\d)/g, '$1 '); }

export function formatExp(v) {
  const n = digits(v).slice(0, 4);
  return n.length > 2 ? `${n.slice(0, 2)}/${n.slice(2)}` : n;
}

/** Valida y devuelve { errors, details } donde details es lo único que se envía. */
export function validateCard({ number, holder, exp, cvv }) {
  const errors = {};
  const n = digits(number);
  const brand = detectBrand(n);
  const validLength = brand === 'visa' ? [13, 16, 19].includes(n.length) : brand === 'mastercard' ? n.length === 16 : false;
  if (!brand) errors['card.number'] = 'Solo aceptamos Visa o Mastercard.';
  else if (!validLength || !luhn(n)) errors['card.number'] = 'El número de tarjeta no es válido.';
  const m = String(exp || '').match(/^(\d{2})\/(\d{2})$/);
  const now = new Date();
  const month = m ? parseInt(m[1], 10) : 0;
  const year = m ? 2000 + parseInt(m[2], 10) : 0;
  if (!m || month < 1 || month > 12 || year < now.getFullYear() || (year === now.getFullYear() && month < now.getMonth() + 1)) {
    errors['card.exp'] = 'Escribe una fecha de vencimiento válida (MM/AA).';
  }
  if (!/^\d{3}$/.test(digits(cvv)) || digits(cvv).length !== String(cvv).trim().length) errors['card.cvv'] = 'El CVV son los 3 dígitos del reverso.';
  if (String(holder || '').trim().length < 3) errors['card.holder'] = 'Escribe el nombre como aparece en la tarjeta.';
  return {
    errors,
    details: { brand, last4: n.slice(-4), exp_month: month, exp_year: year, holder: String(holder || '').trim() },
  };
}
