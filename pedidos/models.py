from collections import defaultdict
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models, transaction
from django.utils import timezone

from inventario.models import EstoqueInsuficiente, Insumo
from inventario.utils import baixar_estoque as baixar_insumos

from .formatacao import numero

ZERO = Decimal("0")
CENTAVOS = Decimal("0.01")


# ---------------------------------------------------------------------------
# Cardápio
# ---------------------------------------------------------------------------
class CategoriaCardapio(models.Model):
    nome = models.CharField(max_length=60, unique=True)
    descricao = models.TextField("descrição", blank=True)
    ordem = models.PositiveSmallIntegerField(
        default=0, help_text="Ordem de exibição no cardápio (menor aparece primeiro)."
    )
    ativa = models.BooleanField(default=True)

    class Meta:
        verbose_name = "categoria do cardápio"
        verbose_name_plural = "categorias do cardápio"
        ordering = ["ordem", "nome"]

    def __str__(self):
        return self.nome


class ItemCardapio(models.Model):
    """Prato, petisco, bebida ou drink vendido ao cliente."""

    nome = models.CharField(max_length=100, unique=True)
    descricao = models.TextField("descrição", blank=True)
    categoria = models.ForeignKey(
        CategoriaCardapio, on_delete=models.PROTECT, related_name="itens"
    )
    preco = models.DecimalField(
        "preço (R$)",
        max_digits=8,
        decimal_places=2,
        validators=[MinValueValidator(CENTAVOS)],
    )
    tempo_preparo = models.PositiveSmallIntegerField("tempo de preparo (min)", default=0)
    disponivel = models.BooleanField("disponível", default=True)
    destaque = models.BooleanField(default=False)
    insumos = models.ManyToManyField(
        Insumo,
        through="FichaTecnica",
        related_name="itens_cardapio",
        blank=True,
    )
    criado_em = models.DateTimeField("cadastrado em", auto_now_add=True)
    atualizado_em = models.DateTimeField("atualizado em", auto_now=True)

    class Meta:
        verbose_name = "item do cardápio"
        verbose_name_plural = "itens do cardápio"
        ordering = ["categoria__ordem", "nome"]

    def __str__(self):
        return self.nome

    @property
    def custo_estimado(self):
        """Soma do custo dos insumos da ficha técnica para uma porção."""
        if not self.pk:
            return ZERO
        total = sum(
            (f.quantidade * f.insumo.custo_unitario for f in self.ficha_tecnica.all()),
            ZERO,
        )
        return total.quantize(CENTAVOS)

    @property
    def margem_percentual(self):
        if not self.preco:
            return None
        return ((self.preco - self.custo_estimado) / self.preco * 100).quantize(Decimal("0.1"))

    def tem_estoque(self, porcoes=1):
        """Verifica se há insumos suficientes para preparar a quantidade pedida."""
        if not self.pk:
            return True
        return all(
            f.insumo.quantidade_estoque >= f.quantidade * porcoes
            for f in self.ficha_tecnica.all()
        )


class FichaTecnica(models.Model):
    """Quanto de cada insumo é consumido em uma porção de um item do cardápio."""

    item = models.ForeignKey(
        ItemCardapio, on_delete=models.CASCADE, related_name="ficha_tecnica"
    )
    insumo = models.ForeignKey(Insumo, on_delete=models.PROTECT, related_name="fichas_tecnicas")
    quantidade = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        validators=[MinValueValidator(Decimal("0.001"))],
        help_text="Na unidade do insumo (ex.: 0,350 kg; 1 un; 0,060 l).",
    )

    class Meta:
        verbose_name = "insumo da ficha técnica"
        verbose_name_plural = "ficha técnica"
        constraints = [
            models.UniqueConstraint(fields=["item", "insumo"], name="ficha_item_insumo_unico"),
        ]

    def __str__(self):
        if not self.insumo_id:
            return "Novo insumo da ficha"
        return f"{numero(self.quantidade)} {self.insumo.unidade.lower()} de {self.insumo.nome}"


# ---------------------------------------------------------------------------
# Mesas e reservas
# ---------------------------------------------------------------------------
class Mesa(models.Model):
    class Status(models.TextChoices):
        LIVRE = "LIVRE", "Livre"
        OCUPADA = "OCUPADA", "Ocupada"
        RESERVADA = "RESERVADA", "Reservada"
        MANUTENCAO = "MANUTENCAO", "Em manutenção"

    class Area(models.TextChoices):
        SALAO = "SALAO", "Salão"
        VARANDA = "VARANDA", "Varanda"
        BALCAO = "BALCAO", "Balcão"
        EXTERNA = "EXTERNA", "Área externa"

    numero = models.PositiveSmallIntegerField("número", unique=True)
    capacidade = models.PositiveSmallIntegerField(default=4, validators=[MinValueValidator(1)])
    area = models.CharField("área", max_length=10, choices=Area.choices, default=Area.SALAO)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.LIVRE)
    ativa = models.BooleanField(default=True)

    class Meta:
        verbose_name = "mesa"
        verbose_name_plural = "mesas"
        ordering = ["numero"]

    def __str__(self):
        return f"Mesa {self.numero:02d}"

    @property
    def comanda_aberta(self):
        if not self.pk:
            return None
        return self.comandas.filter(status=Comanda.Status.ABERTA).first()


class Reserva(models.Model):
    class Status(models.TextChoices):
        PENDENTE = "PENDENTE", "Pendente"
        CONFIRMADA = "CONFIRMADA", "Confirmada"
        CANCELADA = "CANCELADA", "Cancelada"
        CONCLUIDA = "CONCLUIDA", "Concluída"
        NAO_COMPARECEU = "NAO_COMPARECEU", "Não compareceu"

    STATUS_ATIVOS = (Status.PENDENTE, Status.CONFIRMADA)
    DURACAO = timedelta(hours=2)

    cliente = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reservas"
    )
    mesa = models.ForeignKey(
        Mesa,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reservas",
        help_text="Definida pela equipe ao confirmar a reserva.",
    )
    data_hora = models.DateTimeField("data e hora")
    pessoas = models.PositiveSmallIntegerField(default=2, validators=[MinValueValidator(1)])
    status = models.CharField(max_length=15, choices=Status.choices, default=Status.PENDENTE)
    observacao = models.TextField("observação", blank=True)
    criada_em = models.DateTimeField("criada em", auto_now_add=True)

    class Meta:
        verbose_name = "reserva"
        verbose_name_plural = "reservas"
        ordering = ["data_hora"]

    def __str__(self):
        if not self.data_hora:
            return f"Reserva de {self.cliente}"
        return f"Reserva de {self.cliente} — {timezone.localtime(self.data_hora):%d/%m %H:%M}"

    def clean(self):
        erros = {}
        if self.mesa_id and self.pessoas and self.pessoas > self.mesa.capacidade:
            erros["pessoas"] = f"{self.mesa} comporta no máximo {self.mesa.capacidade} pessoas."
        if self._state.adding and self.data_hora and self.data_hora < timezone.now():
            erros["data_hora"] = "A reserva precisa ser para uma data futura."
        if self.mesa_id and self.data_hora and self.status in self.STATUS_ATIVOS:
            conflito = (
                Reserva.objects.filter(
                    mesa_id=self.mesa_id,
                    status__in=self.STATUS_ATIVOS,
                    data_hora__gt=self.data_hora - self.DURACAO,
                    data_hora__lt=self.data_hora + self.DURACAO,
                )
                .exclude(pk=self.pk)
                .exists()
            )
            if conflito:
                erros["mesa"] = "Já existe reserva para esta mesa neste horário (janela de 2 horas)."
        if erros:
            raise ValidationError(erros)


# ---------------------------------------------------------------------------
# Comandas e itens consumidos
# ---------------------------------------------------------------------------
class Comanda(models.Model):
    class Status(models.TextChoices):
        ABERTA = "ABERTA", "Aberta"
        FECHADA = "FECHADA", "Fechada (paga)"
        CANCELADA = "CANCELADA", "Cancelada"

    class FormaPagamento(models.TextChoices):
        DINHEIRO = "DINHEIRO", "Dinheiro"
        PIX = "PIX", "Pix"
        CREDITO = "CREDITO", "Cartão de crédito"
        DEBITO = "DEBITO", "Cartão de débito"
        VALE = "VALE", "Vale-refeição"

    TAXA_SERVICO = Decimal("0.10")

    mesa = models.ForeignKey(Mesa, on_delete=models.PROTECT, related_name="comandas")
    garcom = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="comandas_atendidas",
        verbose_name="garçom",
        limit_choices_to={"perfil__tipo__in": ["GARCOM", "GERENTE"]},
    )
    cliente = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="comandas",
        limit_choices_to={"perfil__tipo": "CLIENTE"},
        help_text="Cliente cadastrado (opcional).",
    )
    nome_cliente = models.CharField(
        "nome do cliente", max_length=100, blank=True, help_text="Para clientes sem cadastro."
    )
    pessoas = models.PositiveSmallIntegerField(default=1, validators=[MinValueValidator(1)])
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ABERTA)
    cobrar_taxa_servico = models.BooleanField("cobrar taxa de serviço (10%)", default=True)
    desconto = models.DecimalField(
        "desconto (R$)",
        max_digits=8,
        decimal_places=2,
        default=ZERO,
        validators=[MinValueValidator(ZERO)],
    )
    forma_pagamento = models.CharField(
        "forma de pagamento", max_length=10, choices=FormaPagamento.choices, blank=True
    )
    observacao = models.TextField("observação", blank=True)
    aberta_em = models.DateTimeField("aberta em", default=timezone.now)
    fechada_em = models.DateTimeField("fechada em", null=True, blank=True)

    class Meta:
        verbose_name = "comanda"
        verbose_name_plural = "comandas"
        ordering = ["-aberta_em"]
        constraints = [
            models.UniqueConstraint(
                fields=["mesa"],
                condition=models.Q(status="ABERTA"),
                name="uma_comanda_aberta_por_mesa",
                violation_error_message="Esta mesa já tem uma comanda aberta.",
            ),
        ]

    def __str__(self):
        if not self.pk:
            return "Nova comanda"
        return f"Comanda #{self.pk} — {self.mesa}"

    # ----- valores -----
    def itens_validos(self):
        if not self.pk:
            return ItemPedido.objects.none()
        return self.itens.exclude(status=ItemPedido.Status.CANCELADO)

    @property
    def subtotal(self):
        return sum((item.subtotal for item in self.itens_validos()), ZERO)

    @property
    def taxa_servico(self):
        if not self.cobrar_taxa_servico:
            return ZERO
        return (self.subtotal * self.TAXA_SERVICO).quantize(CENTAVOS)

    @property
    def total(self):
        return max(self.subtotal + self.taxa_servico - (self.desconto or ZERO), ZERO)

    # ----- regras -----
    def clean(self):
        erros = {}
        if self.mesa_id and self.status == self.Status.ABERTA:
            if self.mesa.status == Mesa.Status.MANUTENCAO:
                erros["mesa"] = "Esta mesa está em manutenção."
            elif (
                Comanda.objects.filter(mesa_id=self.mesa_id, status=self.Status.ABERTA)
                .exclude(pk=self.pk)
                .exists()
            ):
                erros["mesa"] = "Esta mesa já tem uma comanda aberta."
        if self.status == self.Status.FECHADA and not self.forma_pagamento:
            erros["forma_pagamento"] = "Informe a forma de pagamento para fechar a comanda."
        if erros:
            raise ValidationError(erros)

    def save(self, *args, **kwargs):
        with transaction.atomic():
            super().save(*args, **kwargs)
            self._atualizar_status_mesa()

    def _atualizar_status_mesa(self):
        if self.status == self.Status.ABERTA:
            Mesa.objects.filter(pk=self.mesa_id).update(status=Mesa.Status.OCUPADA)
        elif not Comanda.objects.filter(mesa_id=self.mesa_id, status=self.Status.ABERTA).exists():
            Mesa.objects.filter(pk=self.mesa_id, status=Mesa.Status.OCUPADA).update(
                status=Mesa.Status.LIVRE
            )

    def consumo_de_insumos(self):
        """Dicionário {insumo_id: quantidade} consumida pelos itens da comanda."""
        consumo = defaultdict(lambda: ZERO)
        itens = self.itens_validos().prefetch_related("item__ficha_tecnica")
        for pedido in itens:
            for ficha in pedido.item.ficha_tecnica.all():
                consumo[ficha.insumo_id] += ficha.quantidade * pedido.quantidade
        return dict(consumo)

    def baixar_estoque(self, usuario=None):
        """Baixa do estoque tudo o que a comanda consumiu (ou nada, se faltar algo).

        Usa a função baixar_estoque do app inventario, que confere todos os
        insumos antes e registra uma movimentação de saída para cada um.
        """
        consumo = self.consumo_de_insumos()
        if not consumo:
            return []
        try:
            return baixar_insumos(
                consumo,
                usuario=usuario,
                observacao=f"Consumo da comanda #{self.pk} ({self.mesa})",
            )
        except EstoqueInsuficiente as erro:
            faltas = ", ".join(
                f"{insumo.nome} (precisa {numero(necessario)}, há {numero(saldo)})"
                for insumo, necessario, saldo in erro.faltas
            )
            raise ValidationError(f"Estoque insuficiente para fechar a comanda: {faltas}.")

    @transaction.atomic
    def fechar(self, forma_pagamento=None, usuario=None):
        """Fecha a conta: baixa o estoque, registra o pagamento e libera a mesa."""
        if self.status != self.Status.ABERTA:
            raise ValidationError("Só é possível fechar comandas abertas.")
        if forma_pagamento:
            self.forma_pagamento = forma_pagamento
        if not self.forma_pagamento:
            raise ValidationError("Informe a forma de pagamento antes de fechar.")
        if not self.itens_validos().exists():
            raise ValidationError("A comanda não tem itens; cancele-a em vez de fechar.")
        self.baixar_estoque(usuario)
        self.itens.filter(
            status__in=[ItemPedido.Status.PENDENTE, ItemPedido.Status.EM_PREPARO, ItemPedido.Status.PRONTO]
        ).update(status=ItemPedido.Status.ENTREGUE)
        self.status = self.Status.FECHADA
        self.fechada_em = timezone.now()
        self.save()

    @transaction.atomic
    def cancelar(self):
        if self.status != self.Status.ABERTA:
            raise ValidationError("Só é possível cancelar comandas abertas.")
        self.itens.update(status=ItemPedido.Status.CANCELADO)
        self.status = self.Status.CANCELADA
        self.fechada_em = timezone.now()
        self.save()


class ItemPedido(models.Model):
    """Um item do cardápio lançado em uma comanda."""

    class Status(models.TextChoices):
        PENDENTE = "PENDENTE", "Pendente"
        EM_PREPARO = "EM_PREPARO", "Em preparo"
        PRONTO = "PRONTO", "Pronto"
        ENTREGUE = "ENTREGUE", "Entregue"
        CANCELADO = "CANCELADO", "Cancelado"

    STATUS_NA_FILA = (Status.PENDENTE, Status.EM_PREPARO)

    comanda = models.ForeignKey(Comanda, on_delete=models.CASCADE, related_name="itens")
    item = models.ForeignKey(
        ItemCardapio,
        on_delete=models.PROTECT,
        related_name="pedidos",
        verbose_name="item do cardápio",
    )
    quantidade = models.PositiveSmallIntegerField(default=1, validators=[MinValueValidator(1)])
    preco_unitario = models.DecimalField(
        "preço unitário (R$)",
        max_digits=8,
        decimal_places=2,
        blank=True,
        help_text="Copiado do cardápio no momento do pedido.",
    )
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDENTE)
    observacao = models.CharField(
        "observação", max_length=200, blank=True, help_text="Ex.: sem cebola, ponto da carne."
    )
    criado_em = models.DateTimeField("pedido em", auto_now_add=True)
    atualizado_em = models.DateTimeField("atualizado em", auto_now=True)

    class Meta:
        verbose_name = "item do pedido"
        verbose_name_plural = "itens dos pedidos"
        ordering = ["criado_em"]

    def __str__(self):
        nome = self.item.nome if self.item_id else "item"
        return f"{self.quantidade}× {nome}"

    @property
    def subtotal(self):
        preco = self.preco_unitario
        if preco is None:
            preco = self.item.preco if self.item_id else ZERO
        return preco * (self.quantidade or 0)

    def clean(self):
        if not self._state.adding:
            return
        comanda = getattr(self, "comanda", None)
        if comanda is not None and comanda.pk and comanda.status != Comanda.Status.ABERTA:
            raise ValidationError("Não é possível lançar itens em uma comanda fechada ou cancelada.")
        if self.item_id and not self.item.disponivel:
            raise ValidationError({"item": f"{self.item} está indisponível no momento."})

    def save(self, *args, **kwargs):
        if self.preco_unitario is None:
            self.preco_unitario = self.item.preco
        super().save(*args, **kwargs)
