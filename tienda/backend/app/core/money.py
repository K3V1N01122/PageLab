"""Dinero en centavos (enteros). Nunca se usa float para montos."""


def pct_of(amount_cents: int, percent: int) -> int:
    return amount_cents * percent // 100


def clamp(value: int, low: int, high: int) -> int:
    return max(low, min(value, high))
