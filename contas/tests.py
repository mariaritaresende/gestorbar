from io import StringIO

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.test import TestCase

from .models import Perfil

Usuario = get_user_model()


class PerfilTests(TestCase):
    def test_usuario_novo_recebe_perfil_de_cliente(self):
        usuario = Usuario.objects.create_user("joao", password="segredo123")
        self.assertEqual(usuario.perfil.tipo, Perfil.Tipo.CLIENTE)
        self.assertFalse(usuario.is_staff)
        self.assertTrue(usuario.groups.filter(name="Cliente").exists())

    def test_superusuario_recebe_perfil_de_gerente(self):
        usuario = Usuario.objects.create_superuser("chefe", "chefe@exemplo.com", "segredo123")
        self.assertEqual(usuario.perfil.tipo, Perfil.Tipo.GERENTE)

    def test_trocar_para_garcom_libera_o_admin_e_troca_o_grupo(self):
        usuario = Usuario.objects.create_user("maria", password="segredo123")
        perfil = usuario.perfil
        perfil.tipo = Perfil.Tipo.GARCOM
        perfil.save()
        usuario.refresh_from_db()
        self.assertTrue(usuario.is_staff)
        self.assertEqual(list(usuario.groups.values_list("name", flat=True)), ["Garçom"])

    def test_comando_configura_permissoes_dos_grupos(self):
        call_command("configurar_perfis", stdout=StringIO())
        garcom = Group.objects.get(name="Garçom")
        self.assertTrue(garcom.permissions.filter(codename="add_comanda").exists())
        self.assertFalse(garcom.permissions.filter(codename="delete_insumo").exists())
        gerente = Group.objects.get(name="Gerente")
        self.assertTrue(gerente.permissions.filter(codename="delete_insumo").exists())
