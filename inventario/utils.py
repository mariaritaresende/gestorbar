"""Funções de estoque usadas pelo admin e pela app pedidos.

Exemplo (na app pedidos, ao fechar uma comanda):

    from inventario.utils import baixar_estoque
    from inventario.models import EstoqueInsuficiente

    consumo = {insumo_cerveja: Decimal("2"), insumo_limao: Decimal("0.150")}
    try:
        baixar_estoque(consumo, usuario=request.user, observacao="Comanda 12")
    except EstoqueInsuficiente as erro:
        ...  # mostrar erro.faltas ao usuário; NADA foi baixado
"""
from collections import defaultdict
from decimal import Decimal

from django.db import transaction
from django.db.models import F

from .models import EstoqueInsuficiente, Insumo, MovimentacaoEstoque


def _como_decimal(valor):
    return valor if isinstance(valor, Decimal) else Decimal(str(valor))


def registrar_entrada(insumo, quantidade, *, custo_unitario=None, validade=None,
                      usuario=None, observacao=""):
    """Registra uma compra/recebimento e devolve a movimentação criada."""
    return MovimentacaoEstoque.objects.create(
        insumo=insumo,
        tipo=MovimentacaoEstoque.Tipo.ENTRADA,
        quantidade=_como_decimal(quantidade),
        custo_unitario=custo_unitario,
        validade=validade,
        usuario=usuario,
        observacao=observacao,
    )


def registrar_saida(insumo, quantidade, *, tipo=MovimentacaoEstoque.Tipo.SAIDA,
                    usuario=None, observacao=""):
    """Registra uma saída (ou perda). Lança EstoqueInsuficiente se faltar saldo."""
    if tipo not in MovimentacaoEstoque.TIPOS_QUE_DIMINUEM:
        raise ValueError("Use registrar_entrada para entradas.")
    return MovimentacaoEstoque.objects.create(
        insumo=insumo,
        tipo=tipo,
        quantidade=_como_decimal(quantidade),
        usuario=usuario,
        observacao=observacao,
    )


def _agrupar(consumo):
    """Aceita dict {insumo: qtd} ou lista de (insumo, qtd); soma repetidos por id."""
    itens = consumo.items() if isinstance(consumo, dict) else consumo
    total = defaultdict(Decimal)
    for insumo, quantidade in itens:
        insumo_id = insumo.pk if isinstance(insumo, Insumo) else insumo
        total[insumo_id] += _como_decimal(quantidade)
    return {pk: qtd for pk, qtd in total.items() if qtd > 0}


def verificar_disponibilidade(consumo):
    """Devolve a lista de faltas [(insumo, necessario, saldo)]; vazia se tudo há."""
    necessario = _agrupar(consumo)
    insumos = Insumo.objects.in_bulk(necessario.keys())
    return [
        (insumos[pk], qtd, insumos[pk].quantidade_estoque)
        for pk, qtd in necessario.items()
        if insumos[pk].quantidade_estoque < qtd
    ]


@transaction.atomic
def baixar_estoque(consumo, *, usuario=None, observacao=""):
    """Baixa vários insumos de uma vez: ou baixa TODOS, ou não baixa nenhum.

    ``consumo`` é um dict {insumo: quantidade} (ou lista de pares). Se algum
    insumo não tiver saldo, lança EstoqueInsuficiente com todas as faltas e
    a transação é desfeita. Devolve a lista de movimentações criadas.
    """
    necessario = _agrupar(consumo)
    # Trava as linhas em ordem de id (evita deadlock) e confere tudo antes.
    insumos = {
        insumo.pk: insumo
        for insumo in Insumo.objects.select_for_update().filter(pk__in=necessario).order_by("pk")
    }
    faltas = [
        (insumos[pk], qtd, insumos[pk].quantidade_estoque)
        for pk, qtd in necessario.items()
        if insumos[pk].quantidade_estoque < qtd
    ]
    if faltas:
        raise EstoqueInsuficiente(faltas)

    return [
        registrar_saida(insumos[pk], qtd, usuario=usuario, observacao=observacao)
        for pk, qtd in sorted(necessario.items())
    ]


def lista_de_compras(fator=Decimal("2")):
    """Insumos ativos no mínimo ou abaixo, com a quantidade sugerida para repor.

    Sugestão = (estoque mínimo × fator) − saldo atual.
    """
    sugestoes = []
    for insumo in Insumo.objects.ativos().filter(
        quantidade_estoque__lte=F("estoque_minimo")
    ).select_related("fornecedor"):
        alvo = insumo.estoque_minimo * fator
        sugestoes.append((insumo, max(alvo - insumo.quantidade_estoque, Decimal("0"))))
    return sugestoes