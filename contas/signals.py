from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Perfil


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def criar_perfil_do_usuario(sender, instance, created, raw=False, **kwargs):
    """Todo usuário novo ganha um perfil: superusuário vira gerente, o resto cliente."""
    if raw or not created:
        return
    tipo = Perfil.Tipo.GERENTE if instance.is_superuser else Perfil.Tipo.CLIENTE
    Perfil.objects.get_or_create(usuario=instance, defaults={"tipo": tipo})
