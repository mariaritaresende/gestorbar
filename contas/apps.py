from django.apps import AppConfig


class ContasConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "contas"
    verbose_name = "Contas e perfis"

    def ready(self):
        # Registra os sinais (criação automática do perfil de cada usuário).
        from . import signals  # noqa: F401
