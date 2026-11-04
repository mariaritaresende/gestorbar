from datetime import timedelta
from decimal import Decimal

from django.contrib import admin, messages
from django.core.exceptions import ValidationError
from django.db.models import Count, DecimalField, F, Q, Sum
from django.db.models.functions import Coalesce
from django.utils import timezone
from django.utils.html import format_html, format_html_join

from .formatacao import numero, reais
from .models import (
    CategoriaCardapio,
    Comanda,
    FichaTecnica,
    ItemCardapio,
    ItemPedido,
    Mesa,
    Reserva,
)

CORES_STATUS = {
    # Mesa
    "LIVRE": "success",
    "OCUPADA": "danger",
    "RESERVADA": "info",
    "MANUTENCAO": "secondary",
    # Comanda
    "ABERTA": "primary",
    "FECHADA": "success",
    "CANCELADA": "secondary",
    # Item do pedido
    "PENDENTE": "warning",
    "EM_PREPARO": "info",
    "PRONTO": "primary",
    "ENTREGUE": "success",
    "CANCELADO": "secondary",
    # Reserva
    "CONFIRMADA": "success",
    "CONCLUIDA": "dark",
    "NAO_COMPARECEU": "danger",
}


def badge_status(obj):
    cor = CORES_STATUS.get(obj.status, "light")
    return format_html(
        '<span class="badge text-bg-{} badge-status">{}</span>', cor, obj.get_status_display()
    )


# ---------------------------------------------------------------------------
# Filtros personalizados
# ---------------------------------------------------------------------------
class FaixaPrecoFilter(admin.SimpleListFilter):
    title = "faixa de preço"
    parameter_name = "preco"
    FAIXAS = {
        "ate20": ("Até R$ 20", None, Decimal("20")),
        "20a50": ("R$ 20 a R$ 50", Decimal("20"), Decimal("50")),
        "acima50": ("Acima de R$ 50", Decimal("50"), None),
    }

    def lookups(self, request, model_admin):
        return [(chave, rotulo) for chave, (rotulo, _, _) in self.FAIXAS.items()]

    def queryset(self, request, queryset):
        if self.value() not in self.FAIXAS:
            return queryset
        _, minimo, maximo = self.FAIXAS[self.value()]
        if minimo is not None:
            queryset = queryset.filter(preco__gt=minimo)
        if maximo is not None:
            queryset = queryset.filter(preco__lte=maximo)
        return queryset


class EstoqueParaPreparoFilter(admin.SimpleListFilter):
    title = "estoque para preparo"
    parameter_name = "preparo"

    def lookups(self, request, model_admin):
        return [("falta", "Falta algum insumo"), ("sem_ficha", "Sem ficha técnica")]

    def queryset(self, request, queryset):
        if self.value() == "falta":
            return queryset.filter(
                ficha_tecnica__insumo__quantidade_estoque__lt=F("ficha_tecnica__quantidade")
            ).distinct()
        if self.value() == "sem_ficha":
            return queryset.filter(ficha_tecnica__isnull=True)
        return queryset


class FaixaConsumoFilter(admin.SimpleListFilter):
    title = "valor consumido"
    parameter_name = "consumo"

    def lookups(self, request, model_admin):
        return [
            ("vazia", "Sem itens"),
            ("ate100", "Até R$ 100"),
            ("100a300", "R$ 100 a R$ 300"),
            ("acima300", "Acima de R$ 300"),
        ]

    def queryset(self, request, queryset):
        valor = self.value()
        if valor == "vazia":
            return queryset.filter(_subtotal=0)
        if valor == "ate100":
            return queryset.filter(_subtotal__gt=0, _subtotal__lte=100)
        if valor == "100a300":
            return queryset.filter(_subtotal__gt=100, _subtotal__lte=300)
        if valor == "acima300":
            return queryset.filter(_subtotal__gt=300)
        return queryset


class FilaPreparoFilter(admin.SimpleListFilter):
    title = "fila da cozinha/bar"
    parameter_name = "fila"

    def lookups(self, request, model_admin):
        return [("sim", "Na fila (pendente ou em preparo)"), ("atrasado", "Na fila há mais de 20 min")]

    def queryset(self, request, queryset):
        if self.value() in ("sim", "atrasado"):
            queryset = queryset.filter(
                status__in=ItemPedido.STATUS_NA_FILA, comanda__status=Comanda.Status.ABERTA
            )
        if self.value() == "atrasado":
            queryset = queryset.filter(criado_em__lt=timezone.now() - timedelta(minutes=20))
        return queryset


class PeriodoReservaFilter(admin.SimpleListFilter):
    title = "período"
    parameter_name = "periodo"

    def lookups(self, request, model_admin):
        return [("hoje", "Hoje"), ("semana", "Próximos 7 dias"), ("passadas", "Passadas")]

    def queryset(self, request, queryset):
        agora = timezone.now()
        if self.value() == "hoje":
            return queryset.filter(data_hora__date=timezone.localdate())
        if self.value() == "semana":
            return queryset.filter(data_hora__gte=agora, data_hora__lte=agora + timedelta(days=7))
        if self.value() == "passadas":
            return queryset.filter(data_hora__lt=agora)
        return queryset


# ---------------------------------------------------------------------------
# Cardápio
# ---------------------------------------------------------------------------
@admin.register(CategoriaCardapio)
class CategoriaCardapioAdmin(admin.ModelAdmin):
    list_display = ("nome", "ordem", "qtd_itens", "ativa")
    list_editable = ("ordem", "ativa")
    list_filter = ("ativa",)
    search_fields = ("nome",)

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(_qtd_itens=Count("itens"))

    @admin.display(description="itens", ordering="_qtd_itens")
    def qtd_itens(self, obj):
        return obj._qtd_itens


class FichaTecnicaInline(admin.TabularInline):
    model = FichaTecnica
    extra = 1
    autocomplete_fields = ("insumo",)
    fields = ("insumo", "quantidade", "unidade", "custo")
    readonly_fields = ("unidade", "custo")

    @admin.display(description="unidade")
    def unidade(self, obj):
        return obj.insumo.get_unidade_display() if obj.insumo_id else "—"

    @admin.display(description="custo")
    def custo(self, obj):
        if not obj.insumo_id or obj.quantidade is None:
            return "—"
        return reais(obj.quantidade * obj.insumo.custo_unitario)


@admin.register(ItemCardapio)
class ItemCardapioAdmin(admin.ModelAdmin):
    list_display = (
        "nome",
        "categoria",
        "preco",
        "custo",
        "margem",
        "tempo_preparo",
        "estoque_ok",
        "destaque",
        "disponivel",
    )
    list_editable = ("preco", "destaque", "disponivel")
    list_filter = (
        FaixaPrecoFilter,
        EstoqueParaPreparoFilter,
        "categoria",
        "disponivel",
        "destaque",
        ("insumos", admin.RelatedOnlyFieldListFilter),
    )
    search_fields = ("nome", "descricao", "categoria__nome")
    autocomplete_fields = ("categoria",)
    list_select_related = ("categoria",)
    inlines = [FichaTecnicaInline]
    actions = ["marcar_disponivel", "marcar_indisponivel"]
    fieldsets = (
        (None, {"fields": ("nome", "categoria", "descricao")}),
        ("Venda", {"fields": ("preco", "tempo_preparo", "disponivel", "destaque")}),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related("ficha_tecnica__insumo")

    @admin.display(description="custo")
    def custo(self, obj):
        return reais(obj.custo_estimado)

    @admin.display(description="margem")
    def margem(self, obj):
        margem = obj.margem_percentual
        return f"{numero(margem, 1)}%" if margem is not None else "—"

    @admin.display(description="estoque", boolean=True)
    def estoque_ok(self, obj):
        return obj.tem_estoque()

    @admin.action(permissions=["change"], description="Marcar como disponível")
    def marcar_disponivel(self, request, queryset):
        total = queryset.update(disponivel=True)
        self.message_user(request, f"{total} item(ns) disponível(is) no cardápio.", messages.SUCCESS)

    @admin.action(permissions=["change"], description="Marcar como indisponível")
    def marcar_indisponivel(self, request, queryset):
        total = queryset.update(disponivel=False)
        self.message_user(request, f"{total} item(ns) retirado(s) do cardápio.", messages.WARNING)


# ---------------------------------------------------------------------------
# Mesas e reservas
# ---------------------------------------------------------------------------
@admin.register(Mesa)
class MesaAdmin(admin.ModelAdmin):
    list_display = ("__str__", "area", "capacidade", "status_colorido", "comanda_atual", "ativa")
    list_filter = ("status", "area", "capacidade", "ativa")
    search_fields = ("numero",)
    ordering = ("numero",)
    actions = ["liberar", "colocar_em_manutencao"]

    @admin.display(description="status", ordering="status")
    def status_colorido(self, obj):
        return badge_status(obj)

    @admin.display(description="comanda aberta")
    def comanda_atual(self, obj):
        comanda = obj.comanda_aberta
        return f"#{comanda.pk}" if comanda else "—"

    @admin.action(permissions=["change"], description="Liberar mesas (sem comanda aberta)")
    def liberar(self, request, queryset):
        total = queryset.exclude(comandas__status=Comanda.Status.ABERTA).update(
            status=Mesa.Status.LIVRE
        )
        self.message_user(request, f"{total} mesa(s) liberada(s).", messages.SUCCESS)

    @admin.action(permissions=["change"], description="Colocar em manutenção (sem comanda aberta)")
    def colocar_em_manutencao(self, request, queryset):
        total = queryset.exclude(comandas__status=Comanda.Status.ABERTA).update(
            status=Mesa.Status.MANUTENCAO
        )
        self.message_user(request, f"{total} mesa(s) em manutenção.", messages.WARNING)


@admin.register(Reserva)
class ReservaAdmin(admin.ModelAdmin):
    list_display = ("cliente", "data_hora", "pessoas", "mesa", "status_colorido", "criada_em")
    list_filter = (
        PeriodoReservaFilter,
        "status",
        ("mesa", admin.RelatedOnlyFieldListFilter),
        ("data_hora", admin.DateFieldListFilter),
    )
    date_hierarchy = "data_hora"
    search_fields = ("cliente__username", "cliente__first_name", "cliente__last_name", "observacao")
    autocomplete_fields = ("cliente", "mesa")
    list_select_related = ("cliente", "mesa")
    actions = ["confirmar", "cancelar"]

    @admin.display(description="status", ordering="status")
    def status_colorido(self, obj):
        return badge_status(obj)

    @admin.action(permissions=["change"], description="Confirmar reservas selecionadas")
    def confirmar(self, request, queryset):
        total = queryset.filter(status=Reserva.Status.PENDENTE).update(status=Reserva.Status.CONFIRMADA)
        self.message_user(request, f"{total} reserva(s) confirmada(s).", messages.SUCCESS)

    @admin.action(permissions=["change"], description="Cancelar reservas selecionadas")
    def cancelar(self, request, queryset):
        total = queryset.filter(status__in=Reserva.STATUS_ATIVOS).update(status=Reserva.Status.CANCELADA)
        self.message_user(request, f"{total} reserva(s) cancelada(s).", messages.WARNING)


# ---------------------------------------------------------------------------
# Comandas
# ---------------------------------------------------------------------------
class ItemPedidoInline(admin.TabularInline):
    model = ItemPedido
    extra = 1
    autocomplete_fields = ("item",)
    fields = ("item", "quantidade", "observacao", "status", "preco_unitario", "subtotal_formatado")
    readonly_fields = ("preco_unitario", "subtotal_formatado")

    @admin.display(description="subtotal")
    def subtotal_formatado(self, obj):
        return reais(obj.subtotal) if obj.pk else "—"

    # Comanda fechada/cancelada fica somente leitura.
    def _comanda_aberta(self, obj):
        return obj is None or obj.status == Comanda.Status.ABERTA

    def has_add_permission(self, request, obj=None):
        return self._comanda_aberta(obj) and super().has_add_permission(request, obj)

    def has_change_permission(self, request, obj=None):
        return self._comanda_aberta(obj) and super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        return self._comanda_aberta(obj) and super().has_delete_permission(request, obj)


@admin.register(Comanda)
class ComandaAdmin(admin.ModelAdmin):
    list_display = (
        "__str__",
        "cliente_exibicao",
        "garcom",
        "status_colorido",
        "aberta_em",
        "qtd_itens",
        "total_formatado",
        "forma_pagamento",
    )
    list_filter = (
        FaixaConsumoFilter,
        "status",
        "forma_pagamento",
        ("garcom", admin.RelatedOnlyFieldListFilter),
        "mesa__area",
        ("aberta_em", admin.DateFieldListFilter),
        "cobrar_taxa_servico",
    )
    date_hierarchy = "aberta_em"
    search_fields = (
        "nome_cliente",
        "cliente__username",
        "cliente__first_name",
        "garcom__username",
        "garcom__first_name",
        "mesa__numero",
    )
    autocomplete_fields = ("mesa", "garcom", "cliente")
    list_select_related = ("mesa", "garcom", "cliente")
    inlines = [ItemPedidoInline]
    actions = ["fechar_comandas", "cancelar_comandas"]
    fieldsets = (
        ("Atendimento", {"fields": ("mesa", "garcom", "cliente", "nome_cliente", "pessoas", "status")}),
        ("Pagamento", {"fields": ("cobrar_taxa_servico", "desconto", "forma_pagamento", "resumo_valores")}),
        ("Datas e observações", {"fields": ("aberta_em", "fechada_em", "observacao")}),
    )

    def get_queryset(self, request):
        # Anotações usadas na listagem, na ordenação e no filtro "valor consumido".
        return (
            super()
            .get_queryset(request)
            .annotate(
                _qtd_itens=Coalesce(
                    Sum(
                        "itens__quantidade",
                        filter=Q(itens__status__in=self._status_validos()),
                    ),
                    0,
                ),
                _subtotal=Coalesce(
                    Sum(
                        F("itens__quantidade") * F("itens__preco_unitario"),
                        filter=Q(itens__status__in=self._status_validos()),
                        output_field=DecimalField(max_digits=12, decimal_places=2),
                    ),
                    Decimal("0"),
                    output_field=DecimalField(max_digits=12, decimal_places=2),
                ),
            )
        )

    @staticmethod
    def _status_validos():
        return [s for s in ItemPedido.Status.values if s != ItemPedido.Status.CANCELADO]

    def get_readonly_fields(self, request, obj=None):
        # O status muda apenas pelas ações "fechar" e "cancelar" (que baixam o estoque).
        campos = ["status", "fechada_em", "resumo_valores"]
        if obj and obj.status != Comanda.Status.ABERTA:
            return [campo for bloco in self.fieldsets for campo in bloco[1]["fields"]]
        return campos

    def save_model(self, request, obj, form, change):
        if not change and not obj.garcom_id:
            obj.garcom = request.user
        super().save_model(request, obj, form, change)

    @admin.display(description="cliente")
    def cliente_exibicao(self, obj):
        if obj.cliente_id:
            return obj.cliente.get_full_name() or obj.cliente.get_username()
        return obj.nome_cliente or "—"

    @admin.display(description="status", ordering="status")
    def status_colorido(self, obj):
        return badge_status(obj)

    @admin.display(description="itens", ordering="_qtd_itens")
    def qtd_itens(self, obj):
        return obj._qtd_itens

    @admin.display(description="consumo", ordering="_subtotal")
    def total_formatado(self, obj):
        return reais(obj._subtotal)

    @admin.display(description="resumo da conta")
    def resumo_valores(self, obj):
        if not obj or not obj.pk:
            return "Salve a comanda e lance os itens para ver o total."
        linhas = [
            ("Subtotal", reais(obj.subtotal)),
            ("Taxa de serviço", reais(obj.taxa_servico)),
            ("Desconto", f"− {reais(obj.desconto)}"),
            ("Total", reais(obj.total)),
        ]
        return format_html(
            '<table class="resumo-valores">{}</table>',
            format_html_join("", "<tr><td>{}</td><td><strong>{}</strong></td></tr>", linhas),
        )

    @admin.action(permissions=["change"], description="Fechar comandas selecionadas (baixa o estoque)")
    def fechar_comandas(self, request, queryset):
        fechadas = 0
        for comanda in queryset.filter(status=Comanda.Status.ABERTA):
            try:
                comanda.fechar(usuario=request.user)
                fechadas += 1
            except ValidationError as erro:
                self.message_user(request, f"{comanda}: {' '.join(erro.messages)}", messages.ERROR)
        if fechadas:
            self.message_user(request, f"{fechadas} comanda(s) fechada(s).", messages.SUCCESS)

    @admin.action(permissions=["change"], description="Cancelar comandas selecionadas")
    def cancelar_comandas(self, request, queryset):
        canceladas = 0
        for comanda in queryset.filter(status=Comanda.Status.ABERTA):
            comanda.cancelar()
            canceladas += 1
        self.message_user(request, f"{canceladas} comanda(s) cancelada(s).", messages.WARNING)


# ---------------------------------------------------------------------------
# Itens dos pedidos (fila da cozinha/bar)
# ---------------------------------------------------------------------------
@admin.register(ItemPedido)
class ItemPedidoAdmin(admin.ModelAdmin):
    list_display = (
        "__str__",
        "comanda",
        "mesa",
        "observacao",
        "status_colorido",
        "criado_em",
        "espera",
    )
    list_filter = (
        FilaPreparoFilter,
        "status",
        ("item__categoria", admin.RelatedOnlyFieldListFilter),
        "comanda__mesa__area",
        "comanda__status",
        ("criado_em", admin.DateFieldListFilter),
    )
    search_fields = ("item__nome", "observacao", "comanda__mesa__numero")
    list_select_related = ("item", "comanda__mesa")
    autocomplete_fields = ("comanda", "item")
    readonly_fields = ("preco_unitario", "criado_em")
    actions = ["marcar_em_preparo", "marcar_pronto", "marcar_entregue", "marcar_cancelado"]

    @admin.display(description="mesa", ordering="comanda__mesa__numero")
    def mesa(self, obj):
        return obj.comanda.mesa

    @admin.display(description="status", ordering="status")
    def status_colorido(self, obj):
        return badge_status(obj)

    @admin.display(description="espera")
    def espera(self, obj):
        if obj.status not in ItemPedido.STATUS_NA_FILA:
            return "—"
        minutos = int((timezone.now() - obj.criado_em).total_seconds() // 60)
        cor = "danger" if minutos > 20 else "secondary"
        return format_html('<span class="text-{}">{} min</span>', cor, minutos)

    def _mudar_status(self, request, queryset, status):
        total = queryset.filter(comanda__status=Comanda.Status.ABERTA).update(
            status=status, atualizado_em=timezone.now()
        )
        rotulo = ItemPedido.Status(status).label.lower()
        self.message_user(request, f"{total} item(ns) marcado(s) como {rotulo}.", messages.SUCCESS)

    @admin.action(permissions=["change"], description="Marcar como em preparo")
    def marcar_em_preparo(self, request, queryset):
        self._mudar_status(request, queryset, ItemPedido.Status.EM_PREPARO)

    @admin.action(permissions=["change"], description="Marcar como pronto")
    def marcar_pronto(self, request, queryset):
        self._mudar_status(request, queryset, ItemPedido.Status.PRONTO)

    @admin.action(permissions=["change"], description="Marcar como entregue")
    def marcar_entregue(self, request, queryset):
        self._mudar_status(request, queryset, ItemPedido.Status.ENTREGUE)

    @admin.action(permissions=["change"], description="Cancelar itens")
    def marcar_cancelado(self, request, queryset):
        self._mudar_status(request, queryset, ItemPedido.Status.CANCELADO)
