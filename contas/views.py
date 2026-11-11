from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.views import LoginView, LogoutView, PasswordChangeView
from django.shortcuts import redirect
from django.urls import reverse, reverse_lazy
from django.views.generic import CreateView, UpdateView

from .forms import CadastroForm, EntrarForm, PerfilForm, SenhaForm
from .mixins import ClienteRequiredMixin


def destino_apos_login(usuario):
    """Equipe vai para o painel; cliente vai para a área do cliente."""
    if usuario.is_staff:
        return reverse("admin:index")
    return reverse("pedidos:minha_area")


class EntrarView(LoginView):
    template_name = "contas/entrar.html"
    authentication_form = EntrarForm
    redirect_authenticated_user = True

    def get_default_redirect_url(self):
        return destino_apos_login(self.request.user)

    def form_valid(self, form):
        resposta = super().form_valid(form)
        usuario = form.get_user()
        messages.success(self.request, f"Olá, {usuario.first_name or usuario.username}!")
        return resposta


class SairView(LogoutView):
    """Sair da conta (o Django exige POST para o logout)."""

    next_page = "home"

    def post(self, request, *args, **kwargs):
        resposta = super().post(request, *args, **kwargs)
        messages.info(request, "Você saiu da sua conta.")
        return resposta


class CadastroView(CreateView):
    form_class = CadastroForm
    template_name = "contas/cadastro.html"

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect(destino_apos_login(request.user))
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        usuario = form.save()
        login(self.request, usuario, backend="django.contrib.auth.backends.ModelBackend")
        messages.success(
            self.request,
            f"Conta criada. Bem-vindo(a), {usuario.first_name}! Agora você já pode fazer reservas.",
        )
        return redirect("pedidos:minha_area")


class PerfilView(ClienteRequiredMixin, UpdateView):
    form_class = PerfilForm
    template_name = "contas/perfil.html"
    success_url = reverse_lazy("contas:perfil")

    def get_object(self, queryset=None):
        return self.request.user

    def form_valid(self, form):
        messages.success(self.request, "Dados atualizados.")
        return super().form_valid(form)


class TrocarSenhaView(ClienteRequiredMixin, PasswordChangeView):
    form_class = SenhaForm
    template_name = "contas/senha.html"
    success_url = reverse_lazy("contas:perfil")

    def form_valid(self, form):
        messages.success(self.request, "Senha alterada.")
        return super().form_valid(form)
