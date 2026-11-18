from datetime import datetime, time, timedelta

from django import forms
from django.utils import timezone

from contas.forms import BootstrapFormMixin

from .models import Reserva

# Horários aceitos para reserva: das 11h30 às 23h, de meia em meia hora.
HORARIOS = [
    time(h, m)
    for h in range(11, 24)
    for m in (0, 30)
    if time(11, 30) <= time(h, m) <= time(23, 0)
]
ANTECEDENCIA_MINIMA = timedelta(hours=1)
ANTECEDENCIA_MAXIMA = timedelta(days=60)
MAX_PESSOAS = 20


class ReservaForm(BootstrapFormMixin, forms.ModelForm):
    """Reserva feita pelo cliente na área do cliente."""

    data = forms.DateField(label="Data", widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"))
    hora = forms.TypedChoiceField(
        label="Horário",
        choices=[(h.strftime("%H:%M"), h.strftime("%H:%M")) for h in HORARIOS],
        coerce=lambda valor: datetime.strptime(valor, "%H:%M").time(),
    )

    class Meta:
        model = Reserva
        fields = ("pessoas", "observacao")
        labels = {"pessoas": "Quantas pessoas", "observacao": "Observação"}
        widgets = {
            "observacao": forms.Textarea(
                attrs={"rows": 3, "placeholder": "Ex.: aniversário, cadeira para criança, mesa na varanda."}
            ),
        }

    field_order = ("data", "hora", "pessoas", "observacao")

    def __init__(self, *args, cliente=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.cliente = cliente
        hoje = timezone.localdate()
        self.fields["data"].widget.attrs.update(
            {"min": hoje.isoformat(), "max": (hoje + ANTECEDENCIA_MAXIMA).isoformat()}
        )
        self.fields["pessoas"].widget.attrs.update({"min": 1, "max": MAX_PESSOAS})
        if self.instance.pk and self.instance.data_hora:
            local = timezone.localtime(self.instance.data_hora)
            self.fields["data"].initial = local.date()
            self.fields["hora"].initial = local.strftime("%H:%M")

    def clean_pessoas(self):
        pessoas = self.cleaned_data["pessoas"]
        if pessoas > MAX_PESSOAS:
            raise forms.ValidationError(
                f"Para mais de {MAX_PESSOAS} pessoas, fale direto com o bar."
            )
        return pessoas

    def clean(self):
        dados = super().clean()
        data, hora = dados.get("data"), dados.get("hora")
        if not data or not hora:
            return dados

        data_hora = timezone.make_aware(datetime.combine(data, hora))
        agora = timezone.now()
        if data_hora < agora + ANTECEDENCIA_MINIMA:
            self.add_error("hora", "Escolha um horário com pelo menos 1 hora de antecedência.")
            return dados
        if data_hora > agora + ANTECEDENCIA_MAXIMA:
            self.add_error("data", "As reservas abrem com até 60 dias de antecedência.")
            return dados

        if self.cliente is not None:
            mesmo_dia = (
                Reserva.objects.filter(
                    cliente=self.cliente,
                    status__in=Reserva.STATUS_ATIVOS,
                    data_hora__date=data,
                )
                .exclude(pk=self.instance.pk)
                .exists()
            )
            if mesmo_dia:
                self.add_error("data", "Você já tem uma reserva para este dia. Edite a reserva existente.")
                return dados

        # O modelo valida o resto (capacidade da mesa e conflito de horário).
        self.instance.data_hora = data_hora
        return dados
