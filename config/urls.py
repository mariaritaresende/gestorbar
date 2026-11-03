from django.contrib import admin
from django.urls import path
from django.views.generic import TemplateView

urlpatterns = [
    path("admin/", admin.site.urls),
    # Página inicial pública. A área do cliente (login, cadastro etc.)
    # entra no Checkpoint 2.
    path("", TemplateView.as_view(template_name="home.html"), name="home"),
]
