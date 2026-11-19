"""Testes do login, logout, cadastro e perfil do site (área do cliente)."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import Perfil

Usuario = get_user_model()

DADOS_CADASTRO = {
    "first_name": "Joana",
    "last_name": "Lima",
    "email": "joana@exemplo.com",
    "telefone": "(35) 99999-0000",
    "username": "joana",
    "password1": "Mesa-Livre-2026",
    "password2": "Mesa-Livre-2026",
}


class PaginaInicialTests(TestCase):
    def test_visitante_ve_cardapio_e_cadastro(self):
        resposta = self.client.get(reverse("home"))
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, reverse("pedidos:cardapio"))
        self.assertContains(resposta, "Criar conta")

    def test_cliente_logado_ve_atalho_da_minha_area(self):
        cliente = Usuario.objects.create_user("ana", password="senha-segura-1", first_name="Ana")
        self.client.force_login(cliente)
        resposta = self.client.get(reverse("home"))
        self.assertContains(resposta, "Ir para minha área")
        self.assertContains(resposta, "Sair")


class CadastroTests(TestCase):
    def test_pagina_de_cadastro_abre(self):
        resposta = self.client.get(reverse("contas:cadastro"))
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Criar conta")

    def test_cadastro_cria_cliente_e_ja_entra(self):
        resposta = self.client.post(reverse("contas:cadastro"), DADOS_CADASTRO)
        self.assertRedirects(resposta, reverse("pedidos:minha_area"))
        usuario = Usuario.objects.get(username="joana")
        self.assertEqual(usuario.perfil.tipo, Perfil.Tipo.CLIENTE)
        self.assertEqual(usuario.perfil.telefone, "(35) 99999-0000")
        self.assertFalse(usuario.is_staff)
        self.assertEqual(int(self.client.session["_auth_user_id"]), usuario.pk)

    def test_email_repetido_e_recusado(self):
        Usuario.objects.create_user("outra", email="JOANA@exemplo.com", password="x")
        resposta = self.client.post(reverse("contas:cadastro"), DADOS_CADASTRO)
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Já existe uma conta com este e-mail.")
        self.assertFalse(Usuario.objects.filter(username="joana").exists())

    def test_senhas_diferentes_sao_recusadas(self):
        dados = {**DADOS_CADASTRO, "password2": "outra-senha-123"}
        resposta = self.client.post(reverse("contas:cadastro"), dados)
        self.assertEqual(resposta.status_code, 200)
        self.assertFalse(Usuario.objects.filter(username="joana").exists())


class EntrarSairTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cliente = Usuario.objects.create_user("cliente", password="senha-segura-1", first_name="Ana")
        cls.garcom = Usuario.objects.create_user("garcom", password="senha-segura-1")
        perfil = cls.garcom.perfil
        perfil.tipo = Perfil.Tipo.GARCOM
        perfil.save()

    def entrar(self, usuario):
        return self.client.post(
            reverse("contas:entrar"), {"username": usuario, "password": "senha-segura-1"}
        )

    def test_cliente_vai_para_a_minha_area(self):
        self.assertRedirects(self.entrar("cliente"), reverse("pedidos:minha_area"))

    def test_equipe_vai_para_o_painel(self):
        resposta = self.entrar("garcom")
        self.assertRedirects(resposta, reverse("admin:index"), fetch_redirect_response=False)

    def test_senha_errada_mostra_erro(self):
        resposta = self.client.post(reverse("contas:entrar"), {"username": "cliente", "password": "errada"})
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Usuário ou senha incorretos")

    def test_volta_para_a_pagina_pedida(self):
        destino = reverse("pedidos:reservas")
        resposta = self.client.post(
            reverse("contas:entrar") + f"?next={destino}",
            {"username": "cliente", "password": "senha-segura-1", "next": destino},
        )
        self.assertRedirects(resposta, destino)

    def test_sair(self):
        self.client.force_login(self.cliente)
        resposta = self.client.post(reverse("contas:sair"))
        self.assertRedirects(resposta, reverse("home"))
        self.assertNotIn("_auth_user_id", self.client.session)


class PerfilTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cliente = Usuario.objects.create_user(
            "cliente", password="senha-segura-1", first_name="Ana", email="ana@exemplo.com"
        )

    def test_perfil_exige_login(self):
        url = reverse("contas:perfil")
        resposta = self.client.get(url)
        self.assertRedirects(resposta, f"{reverse('contas:entrar')}?next={url}")

    def test_cliente_edita_os_dados(self):
        self.client.force_login(self.cliente)
        resposta = self.client.post(
            reverse("contas:perfil"),
            {"first_name": "Ana Maria", "last_name": "Pereira", "email": "ana@exemplo.com", "telefone": "3599"},
        )
        self.assertRedirects(resposta, reverse("contas:perfil"))
        self.cliente.refresh_from_db()
        self.assertEqual(self.cliente.first_name, "Ana Maria")
        self.assertEqual(self.cliente.perfil.telefone, "3599")

    def test_cliente_troca_a_senha(self):
        self.client.force_login(self.cliente)
        resposta = self.client.post(
            reverse("contas:trocar_senha"),
            {"old_password": "senha-segura-1", "new_password1": "Nova-Senha-2026", "new_password2": "Nova-Senha-2026"},
        )
        self.assertRedirects(resposta, reverse("contas:perfil"))
        self.cliente.refresh_from_db()
        self.assertTrue(self.cliente.check_password("Nova-Senha-2026"))

    def test_equipe_nao_usa_a_area_do_cliente(self):
        gerente = Usuario.objects.create_superuser("chefe", "chefe@exemplo.com", "senha-segura-1")
        self.client.force_login(gerente)
        resposta = self.client.get(reverse("contas:perfil"))
        self.assertRedirects(resposta, reverse("admin:index"))
