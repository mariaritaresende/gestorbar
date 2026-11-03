from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand

from contas.models import Perfil

TODAS = "__all__"

# Permissões de cada perfil, por app. TODAS = todas as permissões do app.
PERMISSOES = {
    Perfil.Tipo.GERENTE: {
        "contas": TODAS,
        "inventario": TODAS,
        "pedidos": TODAS,
        "auth": ["view_user", "add_user", "change_user", "view_group"],
    },
    Perfil.Tipo.GARCOM: {
        "pedidos": [
            "view_mesa", "change_mesa",
            "view_comanda", "add_comanda", "change_comanda",
            "view_itempedido", "add_itempedido", "change_itempedido",
            "view_categoriacardapio", "view_itemcardapio",
            "view_reserva", "add_reserva", "change_reserva",
        ],
    },
    Perfil.Tipo.COZINHA: {
        "pedidos": [
            "view_comanda", "view_itempedido", "change_itempedido",
            "view_categoriacardapio", "view_itemcardapio", "view_fichatecnica",
        ],
        "inventario": [
            "view_insumo", "view_categoriainsumo",
            "view_movimentacaoestoque", "add_movimentacaoestoque",
        ],
    },
    Perfil.Tipo.CLIENTE: {},
}


class Command(BaseCommand):
    help = "Cria os grupos de perfis (Gerente, Garçom, Cozinha/Bar, Cliente) e define suas permissões."

    def handle(self, *args, **options):
        for tipo, por_app in PERMISSOES.items():
            grupo, _ = Group.objects.get_or_create(name=Perfil.nome_grupo(tipo))
            permissoes = []
            for app_label, codenames in por_app.items():
                consulta = Permission.objects.filter(content_type__app_label=app_label)
                if codenames != TODAS:
                    consulta = consulta.filter(codename__in=codenames)
                permissoes.extend(consulta)
            grupo.permissions.set(permissoes)
            self.stdout.write(
                self.style.SUCCESS(f"Grupo '{grupo.name}': {len(permissoes)} permissões")
            )
