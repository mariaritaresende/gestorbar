"""Testes da área do cliente: página "Minha área" e reservas."""
from datetime import timedelta
from decimal import Decimal as D

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import CategoriaCardapio, Comanda, ItemCardapio, ItemPedido, Mesa, Reserva

Usuario = get_user_model()


def daqui_a(dias, hora="20:00"):
    """Data (texto) daqui a N dias e o horário, no formato do formulário."""
    return (timezone.localdate() + timedelta(days=dias)).isoformat(), hora


class AreaDoClienteBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cliente = Usuario.objects.create_user("ana", password="senha-segura-1", first_name="Ana")
        cls.outro = Usuario.objects.create_user("beto", password="senha-segura-1")
        cls.mesa = Mesa.objects.create(numero=1, capacidade=4)

    def setUp(self):
        self.client.force_login(self.cliente)


class MinhaAreaTests(AreaDoClienteBase):
    def test_exige_login(self):
        self.client.logout()
        url = reverse("pedidos:minha_area")
        self.assertRedirects(self.client.get(url), f"{reverse('contas:entrar')}?next={url}")

    def test_mostra_comanda_aberta_e_proxima_reserva(self):
        categoria = CategoriaCardapio.objects.create(nome="Petiscos")
        batata = ItemCardapio.objects.create(nome="Batata frita", categoria=categoria, preco=D("30"))
        comanda = Comanda.objects.create(mesa=self.mesa, cliente=self.cliente)
        ItemPedido.objects.create(comanda=comanda, item=batata, status=ItemPedido.Status.EM_PREPARO)
        Reserva.objects.create(
            cliente=self.cliente, data_hora=timezone.now() + timedelta(days=2), pessoas=3
        )
        resposta = self.client.get(reverse("pedidos:minha_area"))
        self.assertContains(resposta, "Batata frita")
        self.assertContains(resposta, "Em preparo")
        self.assertContains(resposta, "3 pessoas")


class ReservaTests(AreaDoClienteBase):
    def test_cria_reserva_pendente(self):
        data, hora = daqui_a(3)
        resposta = self.client.post(
            reverse("pedidos:reserva_nova"), {"data": data, "hora": hora, "pessoas": 4, "observacao": "Aniversário"}
        )
        self.assertRedirects(resposta, reverse("pedidos:reservas"))
        reserva = Reserva.objects.get()
        self.assertEqual(reserva.cliente, self.cliente)
        self.assertEqual(reserva.status, Reserva.Status.PENDENTE)
        self.assertEqual(timezone.localtime(reserva.data_hora).strftime("%H:%M"), "20:00")

    def test_recusa_horario_no_passado(self):
        ontem = (timezone.localdate() - timedelta(days=1)).isoformat()
        resposta = self.client.post(reverse("pedidos:reserva_nova"), {"data": ontem, "hora": "20:00", "pessoas": 2})
        self.assertEqual(resposta.status_code, 200)
        self.assertFalse(Reserva.objects.exists())

    def test_recusa_duas_reservas_no_mesmo_dia(self):
        data, hora = daqui_a(5)
        self.client.post(reverse("pedidos:reserva_nova"), {"data": data, "hora": hora, "pessoas": 2})
        resposta = self.client.post(reverse("pedidos:reserva_nova"), {"data": data, "hora": "21:00", "pessoas": 2})
        self.assertContains(resposta, "Você já tem uma reserva para este dia")
        self.assertEqual(Reserva.objects.count(), 1)

    def test_alterar_reserva_confirmada_volta_para_pendente(self):
        reserva = Reserva.objects.create(
            cliente=self.cliente,
            mesa=self.mesa,
            data_hora=timezone.now() + timedelta(days=4),
            pessoas=2,
            status=Reserva.Status.CONFIRMADA,
        )
        data, _ = daqui_a(4)
        resposta = self.client.post(
            reverse("pedidos:reserva_editar", args=[reserva.pk]), {"data": data, "hora": "21:30", "pessoas": 3}
        )
        self.assertRedirects(resposta, reverse("pedidos:reservas"))
        reserva.refresh_from_db()
        self.assertEqual(reserva.status, Reserva.Status.PENDENTE)
        self.assertIsNone(reserva.mesa)
        self.assertEqual(reserva.pessoas, 3)

    def test_cancelar_reserva(self):
        reserva = Reserva.objects.create(
            cliente=self.cliente, data_hora=timezone.now() + timedelta(days=2), pessoas=2
        )
        url = reverse("pedidos:reserva_cancelar", args=[reserva.pk])
        self.assertContains(self.client.get(url), "Cancelar reserva")
        self.assertRedirects(self.client.post(url), reverse("pedidos:reservas"))
        reserva.refresh_from_db()
        self.assertEqual(reserva.status, Reserva.Status.CANCELADA)

    def test_cliente_nao_mexe_na_reserva_de_outro(self):
        reserva = Reserva.objects.create(
            cliente=self.outro, data_hora=timezone.now() + timedelta(days=2), pessoas=2
        )
        self.assertEqual(self.client.get(reverse("pedidos:reserva_editar", args=[reserva.pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse("pedidos:reserva_cancelar", args=[reserva.pk])).status_code, 404)

    def test_lista_de_reservas(self):
        Reserva.objects.create(cliente=self.cliente, data_hora=timezone.now() + timedelta(days=2), pessoas=2)
        resposta = self.client.get(reverse("pedidos:reservas"))
        self.assertContains(resposta, "Pendente")
        self.assertContains(resposta, "mesa a definir")
