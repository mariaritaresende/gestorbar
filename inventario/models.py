"""Modelos do inventário: categorias, fornecedores, insumos e movimentações.

Regra principal: o saldo de um insumo (``quantidade_estoque``) NUNCA é editado
à mão. Ele só muda quando uma ``MovimentacaoEstoque`` é registrada (entrada,
saída ou perda). Assim, todo o histórico do estoque fica rastreável.
"""
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models, transaction
from django.utils import timezone

# Dias de antecedência para considerar que um insumo "vence em breve".
DIAS_ALERTA_VALIDADE = 7


class EstoqueInsuficiente(Exception):
    """Lançada quando uma saída deixaria o estoque de algum insumo negativo.

    ``faltas`` é uma lista de tuplas (insumo, quantidade_necessaria, saldo_atual).
    """

    def __init__(self, faltas):
        self.faltas = faltas
        detalhes = "; ".join(
            f"{insumo.nome}: precisa {necessario} {insumo.unidade}, há {saldo}"
            for insumo, necessario, saldo in faltas
        )
        super().__init__(f"Estoque insuficiente — {detalhes}")


class CategoriaInsumo(models.Model):
    """Agrupa os insumos (ex.: Bebidas, Carnes, Hortifruti, Descartáveis)."""

    nome = models.CharField(max_length=60, unique=True)
    descricao = models.TextField("descrição", blank=True)

    class Meta:
        verbose_name = "categoria de insumo"
        verbose_name_plural = "categorias de insumo"
        ordering = ["nome"]

    def __str__(self):
        return self.nome


class Fornecedor(models.Model):
    """Empresa ou pessoa que fornece insumos ao estabelecimento."""

    nome = models.CharField(max_length=120)
    cnpj = models.CharField(
        "CNPJ", max_length=18, unique=True, null=True, blank=True,
        help_text="Formato: 00.000.000/0000-00 (opcional).",
    )
    contato = models.CharField("pessoa de contato", max_length=80, blank=True)
    telefone = models.CharField(max_length=20, blank=True)
    email = models.EmailField("e-mail", blank=True)
    ativo = models.BooleanField(default=True)
    criado_em = models.DateTimeField("criado em", auto_now_add=True)

    class Meta:
        verbose_name = "fornecedor"
        verbose_name_plural = "fornecedores"
        ordering = ["nome"]

    def __str__(self):
        return self.nome

    def save(self, *args, **kwargs):
        # CNPJ vazio vira NULL para não violar o "unique" entre vários vazios.
        if not self.cnpj:
            self.cnpj = None
        super().save(*args, **kwargs)


class InsumoQuerySet(models.QuerySet):
    """Consultas prontas usadas pelos filtros do admin e pela app pedidos."""

    def ativos(self):
        return self.filter(ativo=True)

    def zerados(self):
        return self.filter(quantidade_estoque__lte=0)

    def abaixo_do_minimo(self):
        """Com saldo > 0, porém menor ou igual ao estoque mínimo."""
        return self.filter(
            quantidade_estoque__gt=0,
            quantidade_estoque__lte=models.F("estoque_minimo"),
        )

    def estoque_ok(self):
        return self.filter(quantidade_estoque__gt=models.F("estoque_minimo"))

    def vencidos(self):
        return self.filter(validade__lt=timezone.localdate())

    def vencendo(self, dias=DIAS_ALERTA_VALIDADE):
        hoje = timezone.localdate()
        return self.filter(validade__gte=hoje, validade__lte=hoje + timedelta(days=dias))


class Insumo(models.Model):
    """Matéria-prima ou produto em estoque (ex.: cerveja long neck, picanha, limão)."""

    class Unidade(models.TextChoices):
        UNIDADE = "UN", "Unidade"
        QUILO = "KG", "Quilograma"
        GRAMA = "G", "Grama"
        LITRO = "L", "Litro"
        MILILITRO = "ML", "Mililitro"
        CAIXA = "CX", "Caixa"

    class Situacao(models.TextChoices):
        ZERADO = "ZERADO", "Zerado"
        BAIXO = "BAIXO", "Abaixo do mínimo"
        OK = "OK", "Normal"

    nome = models.CharField(max_length=100, unique=True)
    categoria = models.ForeignKey(
        CategoriaInsumo, on_delete=models.PROTECT, related_name="insumos"
    )
    fornecedor = models.ForeignKey(
        Fornecedor, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="insumos", verbose_name="fornecedor principal",
    )
    unidade = models.CharField(max_length=2, choices=Unidade.choices, default=Unidade.UNIDADE)
    quantidade_estoque = models.DecimalField(
        "quantidade em estoque", max_digits=10, decimal_places=3,
        default=Decimal("0"), editable=False,
        help_text="Atualizada automaticamente pelas movimentações de estoque.",
    )
    estoque_minimo = models.DecimalField(
        "estoque mínimo", max_digits=10, decimal_places=3, default=Decimal("0"),
        validators=[MinValueValidator(Decimal("0"))],
        help_text="Abaixo deste valor o insumo aparece como 'abaixo do mínimo'.",
    )
    custo_unitario = models.DecimalField(
        "custo unitário (R$)", max_digits=10, decimal_places=2, default=Decimal("0"),
        validators=[MinValueValidator(Decimal("0"))],
        help_text="Custo médio ponderado, recalculado a cada entrada com custo.",
    )
    validade = models.DateField(null=True, blank=True, help_text="Validade do lote atual.")
    ativo = models.BooleanField(default=True)
    criado_em = models.DateTimeField("criado em", auto_now_add=True)
    atualizado_em = models.DateTimeField("atualizado em", auto_now=True)

    objects = InsumoQuerySet.as_manager()

    class Meta:
        verbose_name = "insumo"
        verbose_name_plural = "insumos"
        ordering = ["nome"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(quantidade_estoque__gte=0),
                name="insumo_estoque_nao_negativo",
            ),
            models.CheckConstraint(
                condition=models.Q(estoque_minimo__gte=0),
                name="insumo_minimo_nao_negativo",
            ),
        ]

    def __str__(self):
        return f"{self.nome} ({self.get_unidade_display().lower()})"

    @property
    def situacao_estoque(self):
        if self.quantidade_estoque <= 0:
            return self.Situacao.ZERADO
        if self.quantidade_estoque <= self.estoque_minimo:
            return self.Situacao.BAIXO
        return self.Situacao.OK

    @property
    def vencido(self):
        return self.validade is not None and self.validade < timezone.localdate()

    @property
    def vence_em_breve(self):
        if self.validade is None or self.vencido:
            return False
        return self.validade <= timezone.localdate() + timedelta(days=DIAS_ALERTA_VALIDADE)

    @property
    def valor_em_estoque(self):
        return (self.quantidade_estoque * self.custo_unitario).quantize(Decimal("0.01"))


class MovimentacaoEstoque(models.Model):
    """Registro imutável de cada entrada, saída ou perda de um insumo.

    Ao ser salva pela primeira vez, a movimentação atualiza o saldo do insumo
    dentro de uma transação. Uma saída maior que o saldo é recusada.
    """

    class Tipo(models.TextChoices):
        ENTRADA = "ENTRADA", "Entrada (compra/recebimento)"
        SAIDA = "SAIDA", "Saída (consumo/venda)"
        PERDA = "PERDA", "Perda (quebra/vencimento)"

    TIPOS_QUE_DIMINUEM = (Tipo.SAIDA, Tipo.PERDA)

    insumo = models.ForeignKey(
        Insumo, on_delete=models.PROTECT, related_name="movimentacoes"
    )
    tipo = models.CharField(max_length=10, choices=Tipo.choices)
    quantidade = models.DecimalField(
        max_digits=10, decimal_places=3,
        validators=[MinValueValidator(Decimal("0.001"))],
    )
    custo_unitario = models.DecimalField(
        "custo unitário (R$)", max_digits=10, decimal_places=2, null=True, blank=True,
        help_text="Só para entradas: atualiza o custo médio do insumo.",
    )
    validade = models.DateField(
        "validade do lote", null=True, blank=True,
        help_text="Só para entradas: substitui a validade cadastrada no insumo.",
    )
    saldo_apos = models.DecimalField(
        "saldo após", max_digits=10, decimal_places=3, editable=False, default=Decimal("0")
    )
    observacao = models.CharField("observação", max_length=200, blank=True)
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="movimentacoes_estoque", verbose_name="registrado por",
    )
    data = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "movimentação de estoque"
        verbose_name_plural = "movimentações de estoque"
        ordering = ["-data", "-id"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(quantidade__gt=0),
                name="movimentacao_quantidade_positiva",
            ),
        ]

    def __str__(self):
        sinal = "-" if self.diminui_estoque else "+"
        return f"{self.get_tipo_display().split(' (')[0]} {sinal}{self.quantidade} {self.insumo.nome}"

    @property
    def diminui_estoque(self):
        return self.tipo in self.TIPOS_QUE_DIMINUEM

    @property
    def variacao(self):
        """Quantidade com sinal: positiva para entrada, negativa para saída/perda."""
        return -self.quantidade if self.diminui_estoque else self.quantidade

    def clean(self):
        """Validação usada pelo formulário do admin (mostra o erro na tela)."""
        super().clean()
        if self.pk:
            raise ValidationError("Movimentações já registradas não podem ser alteradas.")
        if self.tipo != self.Tipo.ENTRADA and (self.custo_unitario or self.validade):
            raise ValidationError("Custo e validade do lote só se aplicam a entradas.")
        if (
            self.insumo_id
            and self.diminui_estoque
            and self.quantidade
            and self.quantidade > self.insumo.quantidade_estoque
        ):
            raise ValidationError({
                "quantidade": (
                    f"Estoque insuficiente: há {self.insumo.quantidade_estoque} "
                    f"{self.insumo.unidade} de {self.insumo.nome}."
                )
            })

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError("Movimentações já registradas não podem ser alteradas.")
        with transaction.atomic():
            # Trava a linha do insumo para evitar duas baixas simultâneas.
            insumo = Insumo.objects.select_for_update().get(pk=self.insumo_id)
            novo_saldo = insumo.quantidade_estoque + self.variacao
            if novo_saldo < 0:
                raise EstoqueInsuficiente([(insumo, self.quantidade, insumo.quantidade_estoque)])

            campos = ["quantidade_estoque", "atualizado_em"]
            if self.tipo == self.Tipo.ENTRADA and self.custo_unitario is not None:
                # Custo médio ponderado: (valor atual + valor da compra) / novo saldo.
                valor_total = (
                    insumo.quantidade_estoque * insumo.custo_unitario
                    + self.quantidade * self.custo_unitario
                )
                insumo.custo_unitario = (valor_total / novo_saldo).quantize(Decimal("0.01"))
                campos.append("custo_unitario")
            if self.tipo == self.Tipo.ENTRADA and self.validade:
                insumo.validade = self.validade
                campos.append("validade")

            insumo.quantidade_estoque = novo_saldo
            insumo.save(update_fields=campos)
            self.insumo = insumo
            self.saldo_apos = novo_saldo
            super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError(
            "Movimentações não podem ser excluídas; registre uma movimentação inversa."
        )