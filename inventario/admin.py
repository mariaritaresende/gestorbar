"""Painel administrativo do inventário (tema Jazzmin), com filtros personalizados."""
from datetime import timedelta

from django.contrib import admin, messages
from django.db.models import Count
from django.utils import timezone
from django.utils.html import format_html

from .models import (
    DIAS_ALERTA_VALIDADE,
    CategoriaInsumo,
    EstoqueInsuficiente,
    Fornecedor,
    Insumo,
    MovimentacaoEstoque,
)
from .utils import lista_de_compras, registrar_saida

CORES_SITUACAO = {
    Insumo.Situacao.ZERADO: "danger",
    Insumo.Situacao.BAIXO: "warning",
    Insumo.Situacao.OK: "success",
}


# ---------------------------------------------------------------------------
# Filtros personalizados
# ---------------------------------------------------------------------------
class SituacaoEstoqueFilter(admin.SimpleListFilter):
    """Zerado / abaixo do mínimo / normal (compara saldo com o estoque mínimo)."""

    title = "situação do estoque"
    parameter_name = "situacao"

    def lookups(self, request, model_admin):
        return Insumo.Situacao.choices

    def queryset(self, request, queryset):
        filtros = {
            Insumo.Situacao.ZERADO: queryset.zerados,
            Insumo.Situacao.BAIXO: queryset.abaixo_do_minimo,
            Insumo.Situacao.OK: queryset.estoque_ok,
        }
        if self.value() in filtros:
            return filtros[self.value()]()
        return queryset


class ValidadeFilter(admin.SimpleListFilter):
    """Vencidos, vencendo em 7 ou 30 dias, dentro da validade ou sem validade."""

    title = "validade"
    parameter_name = "validade_status"

    def lookups(self, request, model_admin):
        return [
            ("vencido", "Vencido"),
            ("7dias", f"Vence em até {DIAS_ALERTA_VALIDADE} dias"),
            ("30dias", "Vence em até 30 dias"),
            ("valido", "Dentro da validade"),
            ("sem", "Sem validade cadastrada"),
        ]

    def queryset(self, request, queryset):
        hoje = timezone.localdate()
        valor = self.value()
        if valor == "vencido":
            return queryset.vencidos()
        if valor == "7dias":
            return queryset.vencendo(DIAS_ALERTA_VALIDADE)
        if valor == "30dias":
            return queryset.vencendo(30)
        if valor == "valido":
            return queryset.filter(validade__gte=hoje)
        if valor == "sem":
            return queryset.filter(validade__isnull=True)
        return queryset


class PeriodoMovimentacaoFilter(admin.SimpleListFilter):
    """Atalhos de período para o histórico de movimentações."""

    title = "período"
    parameter_name = "periodo"

    def lookups(self, request, model_admin):
        return [("hoje", "Hoje"), ("7", "Últimos 7 dias"), ("30", "Últimos 30 dias")]

    def queryset(self, request, queryset):
        hoje = timezone.localdate()
        if self.value() == "hoje":
            return queryset.filter(data__date=hoje)
        if self.value() in ("7", "30"):
            inicio = hoje - timedelta(days=int(self.value()))
            return queryset.filter(data__date__gte=inicio)
        return queryset


# ---------------------------------------------------------------------------
# Categoria e fornecedor
# ---------------------------------------------------------------------------
@admin.register(CategoriaInsumo)
class CategoriaInsumoAdmin(admin.ModelAdmin):
    list_display = ("nome", "total_insumos", "descricao")
    search_fields = ("nome",)

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(_total=Count("insumos"))

    @admin.display(description="insumos", ordering="_total")
    def total_insumos(self, obj):
        return obj._total


@admin.register(Fornecedor)
class FornecedorAdmin(admin.ModelAdmin):
    list_display = ("nome", "cnpj", "contato", "telefone", "email", "total_insumos", "ativo")
    list_filter = ("ativo",)
    list_editable = ("ativo",)
    search_fields = ("nome", "cnpj", "contato", "email")
    fieldsets = (
        ("Dados do fornecedor", {"fields": ("nome", "cnpj", "ativo")}),
        ("Contato", {"fields": ("contato", "telefone", "email")}),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(_total=Count("insumos"))

    @admin.display(description="insumos", ordering="_total")
    def total_insumos(self, obj):
        return obj._total


# ---------------------------------------------------------------------------
# Insumo
# ---------------------------------------------------------------------------
class MovimentacaoInline(admin.TabularInline):
    """Últimas movimentações exibidas dentro da ficha do insumo (só leitura)."""

    model = MovimentacaoEstoque
    extra = 0
    max_num = 0
    can_delete = False
    show_change_link = True
    verbose_name_plural = "histórico de movimentações"
    fields = ("data", "tipo", "quantidade", "saldo_apos", "usuario", "observacao")
    readonly_fields = fields
    ordering = ("-data",)

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Insumo)
class InsumoAdmin(admin.ModelAdmin):
    list_display = (
        "nome", "categoria", "estoque_formatado", "estoque_minimo",
        "badge_situacao", "badge_validade", "custo_unitario", "valor_em_estoque", "ativo",
    )
    list_display_links = ("nome",)
    list_filter = (
        SituacaoEstoqueFilter, ValidadeFilter, "categoria", "fornecedor", "unidade", "ativo",
    )
    list_select_related = ("categoria", "fornecedor")
    search_fields = ("nome", "categoria__nome", "fornecedor__nome")
    autocomplete_fields = ("categoria", "fornecedor")
    readonly_fields = ("quantidade_estoque", "valor_em_estoque", "criado_em", "atualizado_em")
    list_per_page = 25
    actions = ("baixar_vencidos_como_perda", "mostrar_lista_de_compras", "ativar", "desativar")
    inlines = (MovimentacaoInline,)
    fieldsets = (
        ("Identificação", {"fields": ("nome", "categoria", "fornecedor", "unidade", "ativo")}),
        ("Estoque", {"fields": (
            "quantidade_estoque", "estoque_minimo", "custo_unitario", "valor_em_estoque", "validade",
        )}),
        ("Registro", {"fields": ("criado_em", "atualizado_em")}),
    )

    @admin.display(description="em estoque", ordering="quantidade_estoque")
    def estoque_formatado(self, obj):
        return f"{obj.quantidade_estoque.normalize():f} {obj.unidade}"

    @admin.display(description="situação")
    def badge_situacao(self, obj):
        situacao = obj.situacao_estoque
        return format_html(
            '<span class="badge badge-{0} bg-{0}">{1}</span>',
            CORES_SITUACAO[situacao], situacao.label,
        )

    @admin.display(description="validade", ordering="validade")
    def badge_validade(self, obj):
        if obj.validade is None:
            return "—"
        data = obj.validade.strftime("%d/%m/%Y")
        if obj.vencido:
            return format_html('<span class="badge badge-danger bg-danger">Vencido em {}</span>', data)
        if obj.vence_em_breve:
            return format_html('<span class="badge badge-warning bg-warning">{}</span>', data)
        return data

    @admin.display(description="valor em estoque (R$)")
    def valor_em_estoque(self, obj):
        return obj.valor_em_estoque

    # --- Ações em massa ---------------------------------------------------
    @admin.action(permissions=["change"], description="Baixar insumos vencidos como perda")
    def baixar_vencidos_como_perda(self, request, queryset):
        baixados = 0
        for insumo in queryset.vencidos().filter(quantidade_estoque__gt=0):
            try:
                registrar_saida(
                    insumo, insumo.quantidade_estoque,
                    tipo=MovimentacaoEstoque.Tipo.PERDA,
                    usuario=request.user, observacao="Baixa por vencimento",
                )
                baixados += 1
            except EstoqueInsuficiente as erro:
                self.message_user(request, str(erro), messages.ERROR)
        self.message_user(request, f"{baixados} insumo(s) vencido(s) baixado(s) como perda.")

    @admin.action(description="Mostrar lista de compras (itens no mínimo)")
    def mostrar_lista_de_compras(self, request, queryset):
        selecionados = set(queryset.values_list("pk", flat=True))
        linhas = [
            f"{insumo.nome}: comprar {qtd.normalize():f} {insumo.unidade}"
            + (f" ({insumo.fornecedor})" if insumo.fornecedor else "")
            for insumo, qtd in lista_de_compras()
            if insumo.pk in selecionados
        ]
        if linhas:
            self.message_user(request, "Lista de compras — " + " | ".join(linhas), messages.WARNING)
        else:
            self.message_user(request, "Nenhum insumo selecionado precisa de reposição.")

    @admin.action(permissions=["change"], description="Ativar insumos selecionados")
    def ativar(self, request, queryset):
        self.message_user(request, f"{queryset.update(ativo=True)} insumo(s) ativado(s).")

    @admin.action(permissions=["change"], description="Desativar insumos selecionados")
    def desativar(self, request, queryset):
        self.message_user(request, f"{queryset.update(ativo=False)} insumo(s) desativado(s).")


# ---------------------------------------------------------------------------
# Movimentação de estoque
# ---------------------------------------------------------------------------
@admin.register(MovimentacaoEstoque)
class MovimentacaoEstoqueAdmin(admin.ModelAdmin):
    list_display = (
        "data", "insumo", "tipo_colorido", "quantidade_com_sinal", "saldo_apos",
        "custo_unitario", "usuario", "observacao",
    )
    list_filter = (
        PeriodoMovimentacaoFilter,
        "tipo",
        "insumo__categoria",
        ("usuario", admin.RelatedOnlyFieldListFilter),
    )
    list_select_related = ("insumo", "usuario")
    search_fields = ("insumo__nome", "observacao", "usuario__username")
    autocomplete_fields = ("insumo",)
    date_hierarchy = "data"
    list_per_page = 50
    fieldsets = (
        ("Movimentação", {"fields": ("insumo", "tipo", "quantidade", "observacao")}),
        ("Somente para entradas", {"fields": ("custo_unitario", "validade")}),
    )

    def get_fieldsets(self, request, obj=None):
        if obj:  # registro já salvo: mostra tudo, só leitura
            return (
                ("Movimentação", {"fields": ("insumo", "tipo", "quantidade", "saldo_apos", "observacao")}),
                ("Entrada", {"fields": ("custo_unitario", "validade")}),
                ("Registro", {"fields": ("usuario", "data")}),
            )
        return self.fieldsets

    def get_readonly_fields(self, request, obj=None):
        if obj:
            return ("insumo", "tipo", "quantidade", "saldo_apos", "observacao",
                    "custo_unitario", "validade", "usuario", "data")
        return ()

    def has_change_permission(self, request, obj=None):
        # Permite abrir a tela de detalhes, mas o histórico é imutável.
        return obj is None and super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        obj.usuario = request.user
        super().save_model(request, obj, form, change)

    @admin.display(description="tipo", ordering="tipo")
    def tipo_colorido(self, obj):
        cor = {"ENTRADA": "success", "SAIDA": "info", "PERDA": "danger"}[obj.tipo]
        return format_html('<span class="badge badge-{0} bg-{0}">{1}</span>',
                           cor, obj.get_tipo_display().split(" (")[0])

    @admin.display(description="quantidade", ordering="quantidade")
    def quantidade_com_sinal(self, obj):
        return f"{obj.variacao.normalize():+f} {obj.insumo.unidade}"