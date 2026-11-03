from django.conf import settings
from django.contrib.auth.models import Group
from django.db import models


class Perfil(models.Model):
    """Dados extras do usuário e o papel que ele exerce no estabelecimento.

    O tipo do perfil define o grupo (e portanto as permissões) do usuário:
    gerente, garçom e cozinha/bar acessam o painel administrativo; o cliente
    usa apenas a área do cliente.
    """

    class Tipo(models.TextChoices):
        GERENTE = "GERENTE", "Gerente"
        GARCOM = "GARCOM", "Garçom"
        COZINHA = "COZINHA", "Cozinha/Bar"
        CLIENTE = "CLIENTE", "Cliente"

    TIPOS_EQUIPE = (Tipo.GERENTE, Tipo.GARCOM, Tipo.COZINHA)

    usuario = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="perfil",
        verbose_name="usuário",
    )
    tipo = models.CharField(
        "tipo de perfil", max_length=10, choices=Tipo.choices, default=Tipo.CLIENTE
    )
    telefone = models.CharField(max_length=20, blank=True)
    criado_em = models.DateTimeField("criado em", auto_now_add=True)

    class Meta:
        verbose_name = "perfil"
        verbose_name_plural = "perfis"
        ordering = ["usuario__username"]

    def __str__(self):
        return f"{self.usuario.get_username()} ({self.get_tipo_display()})"

    @property
    def eh_equipe(self):
        return self.tipo in self.TIPOS_EQUIPE

    @classmethod
    def nome_grupo(cls, tipo):
        """Nome do grupo de permissões correspondente a um tipo de perfil."""
        return cls.Tipo(tipo).label

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.sincronizar_acesso()

    def sincronizar_acesso(self):
        """Coloca o usuário no grupo do seu perfil e ajusta o acesso ao admin."""
        usuario = self.usuario
        nomes_grupos = [label for _, label in self.Tipo.choices]
        usuario.groups.remove(*Group.objects.filter(name__in=nomes_grupos))
        grupo, _ = Group.objects.get_or_create(name=self.nome_grupo(self.tipo))
        usuario.groups.add(grupo)

        # Superusuários nunca perdem o acesso ao painel.
        if not usuario.is_superuser and usuario.is_staff != self.eh_equipe:
            type(usuario).objects.filter(pk=usuario.pk).update(is_staff=self.eh_equipe)
            usuario.is_staff = self.eh_equipe
