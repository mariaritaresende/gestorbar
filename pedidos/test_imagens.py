"""Testes das imagens do cardápio: foto do item, ilustração e foto enviada pelo painel."""
from decimal import Decimal as D
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import CategoriaCardapio, ItemCardapio
from .templatetags.site_pedidos import imagem_item

Usuario = get_user_model()


class ImagensDoCardapioTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        drinks = CategoriaCardapio.objects.create(nome="Drinks")
        cls.gin_tonica = ItemCardapio.objects.create(nome="Gin tônica", categoria=drinks, preco=D("34.90"))
        cls.long_neck = ItemCardapio.objects.create(nome="Long neck", categoria=drinks, preco=D("11.90"))

    def test_foto_do_item_vem_antes_da_ilustracao(self):
        # Simula que existem as duas: gin-tonica.jpg e gin-tonica.svg.
        with mock.patch("pedidos.templatetags.site_pedidos.finders.find", return_value="arquivo"):
            self.assertTrue(imagem_item(self.gin_tonica).endswith("img/cardapio/gin-tonica.jpg"))

    def test_sem_foto_usa_a_ilustracao_do_item(self):
        # Simula que só existe a ilustração (gin-tonica.svg).
        def so_svg(caminho):
            return "arquivo" if caminho.endswith(".svg") else None

        with mock.patch("pedidos.templatetags.site_pedidos.finders.find", side_effect=so_svg):
            self.assertTrue(imagem_item(self.gin_tonica).endswith("img/cardapio/gin-tonica.svg"))

    def test_item_sem_imagem_usa_a_generica(self):
        self.assertTrue(imagem_item(self.long_neck).endswith("img/cardapio/generico.svg"))

    def test_foto_enviada_tem_prioridade(self):
        self.long_neck.imagem.name = "cardapio/long-neck.jpg"
        self.assertEqual(imagem_item(self.long_neck), "/media/cardapio/long-neck.jpg")

    def test_cardapio_mostra_as_imagens(self):
        resposta = self.client.get(reverse("pedidos:cardapio"))
        self.assertContains(resposta, "img/cardapio/gin-tonica.")
        self.assertContains(resposta, "img/cardapio/generico.svg")

    def test_tela_do_item_no_painel_mostra_a_imagem(self):
        admin = Usuario.objects.create_superuser("chefe", "chefe@exemplo.com", "senha-segura-1")
        self.client.force_login(admin)
        resposta = self.client.get(reverse("admin:pedidos_itemcardapio_change", args=[self.gin_tonica.pk]))
        self.assertContains(resposta, "imagem padrão do item")
        self.assertContains(resposta, "img/cardapio/gin-tonica.")
