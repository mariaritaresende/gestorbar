"""Telas do site para o cliente, separadas por assunto."""
from .cardapio import CardapioView
from .comandas import ComandaDetailView, ComandaListView
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
    "ReservaCancelarView",
    "ReservaCreateView",
    "ReservaListView",
    "ReservaUpdateView",
]
