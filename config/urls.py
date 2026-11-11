from django.contrib import admin
from django.urls import include, path
from django.views.generic import TemplateView

urlpatterns = [
    # Painel da equipe (Django Admin com Jazzmin).
    path("admin/", admin.site.urls),
    # Site: página inicial e contas do cliente.
    path("", TemplateView.as_view(template_name="home.html"), name="home"),
    path("conta/", include("contas.urls")),
]
