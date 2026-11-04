from decimal import Decimal as D
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from inventario.models import CategoriaInsumo, Insumo, MovimentacaoEstoque
from inventario.utils import registrar_entrada

from .models import CategoriaCardapio, Comanda, FichaTecnica, ItemCardapio, ItemPedido, Mesa


class ComandaTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        categoria_insumo = CategoriaInsumo.objects.create(nome="Cervejas")
        cls.cerveja = Insumo.objects.create(
            nome="Cerveja long neck",
            categoria=categoria_insumo,
            custo_unitario=D("4.00"),
        )
        registrar_entrada(cls.cerveja, D("10"))
        categoria = CategoriaCardapio.objects.create(nome="Bebidas")
        cls.item = ItemCardapio.objects.create(nome="Long neck", categoria=categoria, preco=D("10.00"))
        FichaTecnica.objects.create(item=cls.item, insumo=cls.cerveja, quantidade=D("1"))
        cls.mesa = Mesa.objects.create(numero=1, capacidade=4)

    def abrir_comanda(self, quantidade=3):
        comanda = Comanda.objects.create(mesa=self.mesa)
        ItemPedido.objects.create(comanda=comanda, item=self.item, quantidade=quantidade)
        return comanda

    def test_total_com_taxa_de_servico_e_desconto(self):
        comanda = self.abrir_comanda(3)
        self.assertEqual(comanda.subtotal, D("30.00"))
        self.assertEqual(comanda.taxa_servico, D("3.00"))
        comanda.desconto = D("5.00")
        self.assertEqual(comanda.total, D("28.00"))

    def test_item_cancelado_nao_entra_no_total(self):
        comanda = self.abrir_comanda(3)
        ItemPedido.objects.create(
            comanda=comanda, item=self.item, quantidade=2, status=ItemPedido.Status.CANCELADO
        )
        self.assertEqual(comanda.subtotal, D("30.00"))

    def test_preco_do_pedido_nao_muda_com_o_cardapio(self):
        comanda = self.abrir_comanda(1)
        self.item.preco = D("15.00")
        self.item.save()
        self.assertEqual(comanda.subtotal, D("10.00"))

    def test_abrir_comanda_ocupa_a_mesa(self):
        self.abrir_comanda()
        self.mesa.refresh_from_db()
        self.assertEqual(self.mesa.status, Mesa.Status.OCUPADA)

    def test_fechar_baixa_estoque_e_libera_mesa(self):
        comanda = self.abrir_comanda(3)
        comanda.fechar(forma_pagamento=Comanda.FormaPagamento.PIX)
        self.cerveja.refresh_from_db()
        self.mesa.refresh_from_db()
        self.assertEqual(comanda.status, Comanda.Status.FECHADA)
        self.assertEqual(self.cerveja.quantidade_estoque, D("7"))
        self.assertEqual(self.mesa.status, Mesa.Status.LIVRE)
        saidas = MovimentacaoEstoque.objects.filter(
            insumo=self.cerveja, tipo=MovimentacaoEstoque.Tipo.SAIDA
        )
        self.assertEqual(saidas.count(), 1)
        self.assertEqual(saidas.get().quantidade, D("3"))

    def test_nao_fecha_sem_estoque_suficiente(self):
        comanda = self.abrir_comanda(11)
        with self.assertRaises(ValidationError):
            comanda.fechar(forma_pagamento=Comanda.FormaPagamento.DINHEIRO)
        comanda.refresh_from_db()
        self.cerveja.refresh_from_db()
        self.assertEqual(comanda.status, Comanda.Status.ABERTA)
        self.assertEqual(self.cerveja.quantidade_estoque, D("10"))

    def test_mesa_nao_aceita_duas_comandas_abertas(self):
        self.abrir_comanda()
        with self.assertRaises(ValidationError):
            Comanda(mesa=self.mesa).full_clean()

    def test_nao_lanca_item_em_comanda_fechada(self):
        comanda = self.abrir_comanda(1)
        comanda.fechar(forma_pagamento=Comanda.FormaPagamento.PIX)
        with self.assertRaises(ValidationError):
            ItemPedido(comanda=comanda, item=self.item, quantidade=1).full_clean()


class AdminTests(TestCase):
    """Abre as telas do admin com os dados de exemplo para garantir que nada quebra."""

    @classmethod
    def setUpTestData(cls):
        call_command("popular_dados", stdout=StringIO())
        cls.admin = get_user_model().objects.create_superuser("admin", "admin@exemplo.com", "segredo123")

    def setUp(self):
        self.client.force_login(self.admin)

    def test_painel_inicial(self):
        resposta = self.client.get(reverse("admin:index"))
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Mesas ocupadas")

    def test_listagens_e_filtros(self):
        telas = [
            ("admin:pedidos_comanda_changelist", ["", "?consumo=ate100", "?status__exact=ABERTA"]),
            ("admin:pedidos_itempedido_changelist", ["", "?fila=sim", "?fila=atrasado"]),
            ("admin:pedidos_itemcardapio_changelist", ["", "?preco=20a50", "?preparo=falta"]),
            ("admin:pedidos_mesa_changelist", ["", "?status__exact=OCUPADA"]),
            ("admin:pedidos_reserva_changelist", ["", "?periodo=semana"]),
            ("admin:pedidos_categoriacardapio_changelist", [""]),
            ("admin:inventario_insumo_changelist", ["", "?situacao=BAIXO", "?validade_status=vencido"]),
            ("admin:inventario_movimentacaoestoque_changelist", ["", "?tipo__exact=SAIDA"]),
            ("admin:inventario_fornecedor_changelist", [""]),
            ("admin:inventario_categoriainsumo_changelist", [""]),
            ("admin:contas_perfil_changelist", ["", "?tipo__exact=GARCOM"]),
            ("admin:auth_user_changelist", ["", "?perfil__tipo__exact=CLIENTE"]),
        ]
        for nome_url, filtros in telas:
            for filtro in filtros:
                with self.subTest(tela=nome_url, filtro=filtro):
                    resposta = self.client.get(reverse(nome_url) + filtro)
                    self.assertEqual(resposta.status_code, 200)

    def test_formularios_de_cadastro(self):
        for modelo in ["pedidos_comanda", "pedidos_itemcardapio", "inventario_insumo",
                       "inventario_movimentacaoestoque", "pedidos_reserva"]:
            with self.subTest(modelo=modelo):
                resposta = self.client.get(reverse(f"admin:{modelo}_add"))
                self.assertEqual(resposta.status_code, 200)

    def test_tela_de_edicao_da_comanda(self):
        comanda = Comanda.objects.filter(status=Comanda.Status.ABERTA).first()
        resposta = self.client.get(reverse("admin:pedidos_comanda_change", args=[comanda.pk]))
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Taxa de serviço")

    def test_dados_de_exemplo(self):
        self.assertEqual(Comanda.objects.filter(status=Comanda.Status.FECHADA).count(), 3)
        self.assertEqual(Comanda.objects.filter(status=Comanda.Status.ABERTA).count(), 3)
        self.assertTrue(MovimentacaoEstoque.objects.filter(tipo=MovimentacaoEstoque.Tipo.SAIDA).exists())
