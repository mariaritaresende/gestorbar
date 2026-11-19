"""Telas do site para o cliente, separadas por assunto."""
from .cardapio import CardapioView
from .comandas import ComandaDetailView, ComandaListView
from .minha_area import MinhaAreaView
from .reservas import (
    ReservaCancelarView,
    ReservaCreateView,
    ReservaListView,
    ReservaUpdateView,
)

__all__ = [
    "CardapioView",
    "ComandaDetailView",
    "ComandaListView",
    "MinhaAreaView",
    "ReservaCancelarView",
    "ReservaCreateView",
    "ReservaListView",
    "ReservaUpdateView",
]
