from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect

from .models import Perfil


def eh_cliente(usuario):
    """True se o usuário está logado e tem perfil de cliente."""
    if not usuario.is_authenticated:
        return False
    perfil = getattr(usuario, "perfil", None)
    return perfil is not None and perfil.tipo == Perfil.Tipo.CLIENTE


class ClienteRequiredMixin(LoginRequiredMixin):
    """Protege a área do cliente.

    - Visitante sem login: vai para a tela de entrar (e volta depois).
    - Equipe (gerente, garçom, cozinha): vai para o painel administrativo.
    """

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if not eh_cliente(request.user):
            messages.info(request, "A área do cliente é só para clientes. A equipe usa o painel.")
            return redirect("admin:index")
        return super().dispatch(request, *args, **kwargs)
