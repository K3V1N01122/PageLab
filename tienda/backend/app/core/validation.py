"""Validación de entrada. Todo dato del cliente pasa por aquí."""
import re
import unicodedata

from app.core.errors import ValidationError

EMAIL_RE = re.compile(r"^[^@\s]{1,64}@[^@\s]{1,255}\.[^@\s]{2,}$")
PHONE_RE = re.compile(r"^\+?[0-9 ()-]{7,20}$")
SLUG_RE = re.compile(r"[^a-z0-9]+")


class V:
    """Acumula errores por campo para devolverlos todos juntos."""

    def __init__(self, data):
        if not isinstance(data, dict):
            raise ValidationError("El cuerpo de la solicitud debe ser un objeto JSON.")
        self.data = data
        self.errors: dict[str, str] = {}
        self.out: dict = {}

    def _raw(self, field):
        return self.data.get(field)

    def str(self, field, *, required=True, min_len=0, max_len=255, strip=True, default=None):
        value = self._raw(field)
        if value is None or (isinstance(value, str) and not value.strip()):
            if required:
                self.errors[field] = "Este campo es obligatorio."
            else:
                self.out[field] = default
            return self
        if not isinstance(value, str):
            self.errors[field] = "Debe ser texto."
            return self
        value = value.strip() if strip else value
        if len(value) < min_len:
            self.errors[field] = f"Debe tener al menos {min_len} caracteres."
        elif len(value) > max_len:
            self.errors[field] = f"Debe tener como máximo {max_len} caracteres."
        else:
            self.out[field] = value
        return self

    def email(self, field="email", required=True):
        self.str(field, required=required, max_len=254)
        if field in self.out and self.out[field] is not None:
            value = self.out[field].lower()
            if not EMAIL_RE.match(value):
                self.errors[field] = "Ingresa un correo válido."
                self.out.pop(field)
            else:
                self.out[field] = value
        return self

    def phone(self, field="phone", required=False):
        self.str(field, required=required, max_len=30)
        if self.out.get(field) and not PHONE_RE.match(self.out[field]):
            self.errors[field] = "Ingresa un teléfono válido."
            self.out.pop(field)
        return self

    def int(self, field, *, required=True, min_value=None, max_value=None, default=None):
        value = self._raw(field)
        if value is None or value == "":
            if required:
                self.errors[field] = "Este campo es obligatorio."
            else:
                self.out[field] = default
            return self
        if isinstance(value, bool):
            self.errors[field] = "Debe ser un número entero."
            return self
        try:
            value = int(value)
        except (TypeError, ValueError):
            self.errors[field] = "Debe ser un número entero."
            return self
        if min_value is not None and value < min_value:
            self.errors[field] = f"Debe ser mayor o igual a {min_value}."
        elif max_value is not None and value > max_value:
            self.errors[field] = f"Debe ser menor o igual a {max_value}."
        else:
            self.out[field] = value
        return self

    def bool(self, field, default=False):
        value = self._raw(field)
        self.out[field] = default if value is None else bool(value)
        return self

    def choice(self, field, options, *, required=True, default=None):
        value = self._raw(field)
        if value is None:
            if required:
                self.errors[field] = "Este campo es obligatorio."
            else:
                self.out[field] = default
            return self
        if value not in options:
            self.errors[field] = "Opción no válida."
        else:
            self.out[field] = value
        return self

    def password(self, field="password"):
        value = self._raw(field)
        if not isinstance(value, str) or not value:
            self.errors[field] = "Este campo es obligatorio."
            return self
        if len(value) < 8:
            self.errors[field] = "La contraseña debe tener al menos 8 caracteres."
        elif len(value) > 128:
            self.errors[field] = "La contraseña es demasiado larga."
        elif not (re.search(r"[A-Za-z]", value) and re.search(r"[0-9]", value)):
            self.errors[field] = "Incluye letras y números."
        else:
            self.out[field] = value
        return self

    def check(self):
        if self.errors:
            raise ValidationError("Revisa los campos marcados.", details=self.errors)
        return self.out


def slugify(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    return SLUG_RE.sub("-", text).strip("-")[:200] or "item"


def search_normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"\s+", " ", text).strip()
