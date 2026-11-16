"""Testes do cardápio do site e das contas (comandas) do cliente."""
from decimal import Decimal as D

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from inventario.models import CategoriaInsumo, Insumo
from inventario.utils import registrar_entrada

from .models import (
    CategoriaCardapio,
    Comanda,
    FichaTecnica,
    ItemCardapio,
    ItemPedido,
    Mesa,
)

Usuario = get_user_model()


class AreaDoClienteBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cliente = Usuario.objects.create_user("ana", password="senha-segura-1", first_name="Ana")
        cls.outro = Usuario.objects.create_user("beto", password="senha-segura-1")
        cls.mesa = Mesa.objects.create(numero=1, capacidade=4)

    def setUp(self):
        self.client.force_login(self.cliente)


class CardapioTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        categoria_insumo = CategoriaInsumo.objects.create(nome="Bebidas")
        cerveja = Insumo.objects.create(nome="Cerveja", categoria=categoria_insumo)
        registrar_entrada(cerveja, 10)
        gin = Insumo.objects.create(nome="Gin", categoria=categoria_insumo)  # sem estoque
        drinks = CategoriaCardapio.objects.create(nome="Drinks")
        cls.long_neck = ItemCardapio.objects.create(nome="Long neck", categoria=drinks, preco=D("11.90"))
        FichaTecnica.objects.create(item=cls.long_neck, insumo=cerveja, quantidade=D("1"))
        cls.gin_tonica = ItemCardapio.objects.create(nome="Gin tônica", categoria=drinks, preco=D("34.90"))
        FichaTecnica.objects.create(item=cls.gin_tonica, insumo=gin, quantidade=D("0.06"))
        ItemCardapio.objects.create(nome="Prato fora do ar", categoria=drinks, preco=D("10"), disponivel=False)

    def test_cardapio_e_publico_e_marca_esgotado(self):
        resposta = self.client.get(reverse("pedidos:cardapio"))
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Long neck")
        self.assertContains(resposta, "R$ 11,90")
        self.assertContains(resposta, "Esgotado", count=1)
        self.assertNotContains(resposta, "Prato fora do ar")

    def test_busca(self):
        resposta = self.client.get(reverse("pedidos:cardapio"), {"q": "gin"})
        self.assertContains(resposta, "Gin tônica")
        self.assertNotContains(resposta, "Long neck")


class ComandaDoClienteTests(AreaDoClienteBase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        categoria = CategoriaCardapio.objects.create(nome="Bebidas")
        refri = ItemCardapio.objects.create(nome="Refrigerante", categoria=categoria, preco=D("7.50"))
        cls.minha = Comanda.objects.create(mesa=cls.mesa, cliente=cls.cliente)
        ItemPedido.objects.create(comanda=cls.minha, item=refri, quantidade=2)
        mesa2 = Mesa.objects.create(numero=2)
        cls.alheia = Comanda.objects.create(mesa=mesa2, cliente=cls.outro)

    def test_lista_so_as_comandas_do_cliente(self):
        resposta = self.client.get(reverse("pedidos:comandas"))
        self.assertContains(resposta, f"#{self.minha.pk}")
        self.assertNotContains(resposta, f"#{self.alheia.pk}<")

    def test_detalhe_com_total(self):
        resposta = self.client.get(reverse("pedidos:comanda", args=[self.minha.pk]))
        self.assertContains(resposta, "2× Refrigerante")
        self.assertContains(resposta, "R$ 16,50")  # 15,00 + 10% de serviço

    def test_nao_ve_comanda_de_outro_cliente(self):
        resposta = self.client.get(reverse("pedidos:comanda", args=[self.alheia.pk]))
        self.assertEqual(resposta.status_code, 404)