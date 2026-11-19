from django.urls import path

from . import views

app_name = "contas"

urlpatterns = [
    path("entrar/", views.EntrarView.as_view(), name="entrar"),
    path("sair/", views.SairView.as_view(), name="sair"),
    path("cadastro/", views.CadastroView.as_view(), name="cadastro"),
    path("perfil/", views.PerfilView.as_view(), name="perfil"),
    path("perfil/senha/", views.TrocarSenhaView.as_view(), name="trocar_senha"),
]
