"""Filtros usados nas páginas do site (área do cliente e cardápio)."""
from django import template
from django.contrib.staticfiles import finders
from django.templatetags.static import static
from django.utils.text import slugify

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


@register.filter
def imagem_item(item):
    """Endereço da imagem de um item do cardápio.

    Ordem de preferência:
    1. a foto enviada pelo gerente no painel;
    2. a foto do item em static/img/cardapio/<nome-do-item>.jpg;
    3. a ilustração do item em static/img/cardapio/<nome-do-item>.svg;
    4. uma ilustração genérica.
    """
    if getattr(item, "imagem", None):
        return item.imagem.url
    nome = slugify(item.nome)
    for extensao in ("jpg", "svg"):
        caminho = f"img/cardapio/{nome}.{extensao}"
        if finders.find(caminho):
            return static(caminho)
    return static("img/cardapio/generico.svg")
