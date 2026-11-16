"""Telas do site para o cliente, separadas por assunto."""
from .cardapio import CardapioView
from .comandas import ComandaDetailView, ComandaListView

__all__ = [
    "CardapioView",
    "ComandaDetailView",
    "ComandaListView",
]