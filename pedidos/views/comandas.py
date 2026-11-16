"""Contas (comandas) do cliente: lista e detalhe, só das comandas dele."""
from django.views.generic import DetailView, ListView

from contas.mixins import ClienteRequiredMixin

from ..models import Comanda


class ComandasDoClienteMixin(ClienteRequiredMixin):
    def get_queryset(self):
        return Comanda.objects.filter(cliente=self.request.user).select_related("mesa", "garcom")


class ComandaListView(ComandasDoClienteMixin, ListView):
    template_name = "pedidos/comandas/lista.html"
    context_object_name = "comandas"
    paginate_by = 10

    def get_queryset(self):
        return super().get_queryset().exclude(status=Comanda.Status.CANCELADA).order_by("-aberta_em")


class ComandaDetailView(ComandasDoClienteMixin, DetailView):
    template_name = "pedidos/comandas/detalhe.html"
    context_object_name = "comanda"

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        contexto["itens"] = self.object.itens.select_related("item").order_by("criado_em")
        return contexto