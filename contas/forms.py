from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import (
    AuthenticationForm,
    PasswordChangeForm,
    UserCreationForm,
)

from .models import Perfil

Usuario = get_user_model()


class BootstrapFormMixin:
    """Aplica as classes do Bootstrap aos campos e marca os campos com erro."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for campo in self.fields.values():
            widget = campo.widget
            if isinstance(widget, forms.CheckboxInput):
                classe = "form-check-input"
            elif isinstance(widget, forms.Select):
                classe = "form-select"
            else:
                classe = "form-control"
            widget.attrs.setdefault("class", classe)

    def full_clean(self):
        super().full_clean()
        for nome in self.errors:
            if nome in self.fields:
                widget = self.fields[nome].widget
                widget.attrs["class"] = f"{widget.attrs.get('class', '')} is-invalid".strip()


class EntrarForm(BootstrapFormMixin, AuthenticationForm):
    error_messages = {
        "invalid_login": "Usuário ou senha incorretos. Confira e tente de novo.",
        "inactive": "Esta conta está desativada. Fale com a equipe do bar.",
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].label = "Usuário"
        self.fields["username"].widget.attrs.update({"autocomplete": "username", "autofocus": True})
        self.fields["password"].widget.attrs.update({"autocomplete": "current-password"})


class CadastroForm(BootstrapFormMixin, UserCreationForm):
    """Cadastro de cliente: cria o usuário, e o perfil de cliente é criado pelo sinal."""

    first_name = forms.CharField(label="Nome", max_length=150)
    last_name = forms.CharField(label="Sobrenome", max_length=150, required=False)
    email = forms.EmailField(label="E-mail")
    telefone = forms.CharField(
        label="Telefone",
        max_length=20,
        required=False,
        help_text="Opcional. Usado para avisar sobre a sua reserva.",
    )

    class Meta(UserCreationForm.Meta):
        model = Usuario
        fields = ("first_name", "last_name", "email", "telefone", "username")
        labels = {"username": "Nome de usuário"}
        help_texts = {"username": "Usado para entrar. Letras, números e @ . + - _"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["email"].widget.attrs["autocomplete"] = "email"
        self.fields["telefone"].widget.attrs.update({"autocomplete": "tel", "placeholder": "(35) 99999-0000"})
        self.fields["username"].widget.attrs["autocomplete"] = "username"

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if Usuario.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("Já existe uma conta com este e-mail.")
        return email

    def save(self, commit=True):
        usuario = super().save(commit=False)
        usuario.first_name = self.cleaned_data["first_name"]
        usuario.last_name = self.cleaned_data.get("last_name", "")
        usuario.email = self.cleaned_data["email"]
        if commit:
            usuario.save()  # o sinal cria o Perfil com tipo "cliente"
            perfil = usuario.perfil
            perfil.telefone = self.cleaned_data.get("telefone", "")
            perfil.save()
        return usuario


class PerfilForm(BootstrapFormMixin, forms.ModelForm):
    """Edição dos dados do cliente (usuário + telefone do perfil)."""

    telefone = forms.CharField(label="Telefone", max_length=20, required=False)

    class Meta:
        model = Usuario
        fields = ("first_name", "last_name", "email")
        labels = {"first_name": "Nome", "last_name": "Sobrenome", "email": "E-mail"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["first_name"].required = True
        self.fields["email"].required = True
        perfil = getattr(self.instance, "perfil", None)
        if perfil is not None:
            self.fields["telefone"].initial = perfil.telefone

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if Usuario.objects.filter(email__iexact=email).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("Já existe outra conta com este e-mail.")
        return email

    def save(self, commit=True):
        usuario = super().save(commit=commit)
        if commit:
            perfil, _ = Perfil.objects.get_or_create(usuario=usuario)
            perfil.telefone = self.cleaned_data.get("telefone", "")
            perfil.save()
        return usuario


class SenhaForm(BootstrapFormMixin, PasswordChangeForm):
    pass
