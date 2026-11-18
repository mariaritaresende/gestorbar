from django.urls import path

from . import views

app_name = "pedidos"

urlpatterns = [
    path("cardapio/", views.CardapioView.as_view(), name="cardapio"),
    path("minha-area/", views.MinhaAreaView.as_view(), name="minha_area"),
    path("minha-area/reservas/", views.ReservaListView.as_view(), name="reservas"),
    path("minha-area/reservas/nova/", views.ReservaCreateView.as_view(), name="reserva_nova"),
    path("minha-area/reservas/<int:pk>/editar/", views.ReservaUpdateView.as_view(), name="reserva_editar"),
    path("minha-area/reservas/<int:pk>/cancelar/", views.ReservaCancelarView.as_view(), name="reserva_cancelar"),
    path("minha-area/comandas/", views.ComandaListView.as_view(), name="comandas"),
    path("minha-area/comandas/<int:pk>/", views.ComandaDetailView.as_view(), name="comanda"),
]
