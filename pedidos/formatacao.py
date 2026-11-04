"""Formatação de valores no padrão brasileiro, usada nos painéis do admin."""
from decimal import Decimal


def reais(valor):
    """Decimal('1234.5') -> 'R$ 1.234,50'."""
    if valor is None:
        return "—"
    texto = f"{Decimal(valor):,.2f}"
    return "R$ " + texto.replace(",", "X").replace(".", ",").replace("X", ".")


def numero(valor, casas=3):
    """Decimal('2.500') -> '2,5' (remove zeros à direita)."""
    if valor is None:
        return "—"
    texto = f"{Decimal(valor):.{casas}f}"
    if "." in texto:
        texto = texto.rstrip("0").rstrip(".")
    return texto.replace(".", ",")
