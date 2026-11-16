"""Filtros usados nas páginas do site (área do cliente e cardápio)."""
from django import template

from pedidos.formatacao import reais as formatar_reais

register = template.Library()

# Cor do Bootstrap para cada status (comanda, item e reserva).
CORES = {
    "ABERTA": "primary",
    "FECHADA": "success",
    "CANCELADA": "secondary",
    "PENDENTE": "warning",
    "EM_PREPARO": "info",
    "PRONTO": "primary",
    "ENTREGUE": "success",
    "CANCELADO": "secondary",
    "CONFIRMADA": "success",
    "CONCLUIDA": "dark",
    "NAO_COMPARECEU": "danger",
}


@register.filter
def reais(valor):
    return formatar_reais(valor)


@register.filter
def cor_status(status):
    return CORES.get(status, "secondary")