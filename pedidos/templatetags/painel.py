from decimal import Decimal

from django import template
from django.utils import timezone

from inventario.models import Insumo
from pedidos.formatacao import reais
from pedidos.models import Comanda, ItemPedido, Mesa

register = template.Library()


@register.simple_tag
def painel_resumo():
    """Números exibidos nos cartões do painel inicial do admin."""
    hoje = timezone.localdate()
    fechadas_hoje = Comanda.objects.filter(
        status=Comanda.Status.FECHADA, fechada_em__date=hoje
    )
    faturamento = sum((comanda.total for comanda in fechadas_hoje), Decimal("0"))
    insumos_ativos = Insumo.objects.ativos()
    return {
        "mesas_ocupadas": Mesa.objects.filter(status=Mesa.Status.OCUPADA).count(),
        "mesas_total": Mesa.objects.filter(ativa=True).count(),
        "comandas_abertas": Comanda.objects.filter(status=Comanda.Status.ABERTA).count(),
        "faturamento_hoje": reais(faturamento),
        "itens_pendentes": ItemPedido.objects.filter(
            status__in=ItemPedido.STATUS_NA_FILA, comanda__status=Comanda.Status.ABERTA
        ).count(),
        # Consultas prontas do app inventario (InsumoQuerySet).
        "insumos_baixos": insumos_ativos.abaixo_do_minimo().count(),
        "insumos_zerados": insumos_ativos.zerados().count(),
    }
