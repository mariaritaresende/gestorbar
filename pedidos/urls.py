from django.urls import path

from . import views

app_name = "pedidos"

urlpatterns = [
    path("cardapio/", views.CardapioView.as_view(), name="cardapio"),
    path("minha-area/comandas/", views.ComandaListView.as_view(), name="comandas"),
    path("minha-area/comandas/<int:pk>/", views.ComandaDetailView.as_view(), name="comanda"),
]