"""Página inicial da área do cliente ("Minha área")."""
from decimal import Decimal

from django.utils import timezone
from django.views.generic import TemplateView

from contas.mixins import ClienteRequiredMixin

from ..models import Comanda, ItemPedido, Reserva


class MinhaAreaView(ClienteRequiredMixin, TemplateView):
    template_name = "pedidos/minha_area.html"

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        cliente = self.request.user
        agora = timezone.now()

        fechadas = list(
            cliente.comandas.filter(status=Comanda.Status.FECHADA)
            .select_related("mesa")
            .order_by("-fechada_em")
        )
        comanda_aberta = (
            cliente.comandas.filter(status=Comanda.Status.ABERTA)
            .select_related("mesa", "garcom")
            .prefetch_related("itens__item")
            .first()
        )
        contexto.update(
            {
                "proxima_reserva": cliente.reservas.filter(
                    status__in=Reserva.STATUS_ATIVOS, data_hora__gte=agora
                )
                .select_related("mesa")
                .order_by("data_hora")
                .first(),
                "comanda_aberta": comanda_aberta,
                "itens_abertos": comanda_aberta.itens.exclude(status=ItemPedido.Status.CANCELADO)
                if comanda_aberta
                else [],
                "ultimas_comandas": fechadas[:3],
                "total_visitas": len(fechadas),
                "total_gasto": sum((c.total for c in fechadas), Decimal("0")),
            }
        )
        return contexto
