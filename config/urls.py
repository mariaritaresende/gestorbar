from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from django.views.generic import TemplateView

urlpatterns = [
    # Painel da equipe (Django Admin com Jazzmin).
    path("admin/", admin.site.urls),
    # Site: página inicial, contas do cliente e área do cliente.
    path("", TemplateView.as_view(template_name="home.html"), name="home"),
    path("conta/", include("contas.urls")),
    path("", include("pedidos.urls")),
]

# Em desenvolvimento, o próprio Django serve as fotos enviadas pelo painel.
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
