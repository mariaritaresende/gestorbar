from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import Perfil

Usuario = get_user_model()


class PerfilInline(admin.StackedInline):
    model = Perfil
    can_delete = False
    extra = 0
    max_num = 1
    fields = ("tipo", "telefone")
    verbose_name_plural = "perfil"


# Substitui o admin padrão de usuários para mostrar e filtrar pelo perfil.
admin.site.unregister(Usuario)


@admin.register(Usuario)
class UsuarioAdmin(BaseUserAdmin):
    list_display = (
        "username",
        "nome_completo",
        "email",
        "tipo_perfil",
        "is_staff",
        "is_active",
        "last_login",
    )
    list_filter = (
        "perfil__tipo",
        "is_staff",
        "is_active",
        "groups",
        ("date_joined", admin.DateFieldListFilter),
    )
    list_select_related = ("perfil",)

    def get_inlines(self, request, obj):
        # Na criação o perfil é gerado pelo sinal; o inline aparece só na edição.
        return [PerfilInline] if obj else []

    @admin.display(description="nome")
    def nome_completo(self, obj):
        return obj.get_full_name() or "—"

    @admin.display(description="perfil", ordering="perfil__tipo")
    def tipo_perfil(self, obj):
        perfil = getattr(obj, "perfil", None)
        return perfil.get_tipo_display() if perfil else "—"


@admin.register(Perfil)
class PerfilAdmin(admin.ModelAdmin):
    list_display = ("usuario", "nome", "tipo", "telefone", "criado_em")
    list_filter = ("tipo", ("criado_em", admin.DateFieldListFilter))
    search_fields = ("usuario__username", "usuario__first_name", "usuario__last_name", "telefone")
    list_select_related = ("usuario",)
    readonly_fields = ("usuario", "criado_em")
    fields = ("usuario", "tipo", "telefone", "criado_em")

    @admin.display(description="nome", ordering="usuario__first_name")
    def nome(self, obj):
        return obj.usuario.get_full_name() or "—"

    # O perfil nasce e morre junto com o usuário.
    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
