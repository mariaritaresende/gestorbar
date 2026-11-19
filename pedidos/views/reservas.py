"""Reservas do cliente: criar, consultar, alterar e cancelar."""
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.views import View
from django.views.generic import CreateView, ListView, UpdateView

from contas.mixins import ClienteRequiredMixin

from ..forms import ReservaForm
from ..models import Reserva


class ReservasDoClienteMixin(ClienteRequiredMixin):
    def get_queryset(self):
        return Reserva.objects.filter(cliente=self.request.user).select_related("mesa")


class ReservaListView(ReservasDoClienteMixin, ListView):
    template_name = "pedidos/reservas/lista.html"
    context_object_name = "reservas"

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        reservas = list(contexto["reservas"].order_by("data_hora"))
        contexto["proximas"] = [r for r in reservas if r.pode_alterar]
        contexto["anteriores"] = sorted(
            (r for r in reservas if not r.pode_alterar), key=lambda r: r.data_hora, reverse=True
        )
        return contexto


class ReservaFormMixin:
    form_class = ReservaForm
    template_name = "pedidos/reservas/form.html"
    success_url = reverse_lazy("pedidos:reservas")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["cliente"] = self.request.user
        return kwargs


class ReservaCreateView(ClienteRequiredMixin, ReservaFormMixin, CreateView):
    def form_valid(self, form):
        form.instance.cliente = self.request.user
        form.instance.status = Reserva.Status.PENDENTE
        messages.success(self.request, "Reserva enviada. A equipe vai confirmar e escolher a sua mesa.")
        return super().form_valid(form)


class ReservaUpdateView(ReservasDoClienteMixin, ReservaFormMixin, UpdateView):
    def get_queryset(self):
        # Só reservas ativas e futuras podem ser editadas.
        return super().get_queryset().filter(
            status__in=Reserva.STATUS_ATIVOS, data_hora__gt=timezone.now()
        )

    def form_valid(self, form):
        if form.instance.status == Reserva.Status.CONFIRMADA:
            # Mudou a reserva confirmada: volta para a equipe conferir a mesa.
            form.instance.status = Reserva.Status.PENDENTE
            form.instance.mesa = None
            messages.info(self.request, "Reserva alterada. Ela volta para a equipe confirmar.")
        else:
            messages.success(self.request, "Reserva alterada.")
        return super().form_valid(form)


class ReservaCancelarView(ClienteRequiredMixin, View):
    template_name = "pedidos/reservas/cancelar.html"

    def get_reserva(self):
        return get_object_or_404(
            Reserva,
            pk=self.kwargs["pk"],
            cliente=self.request.user,
            status__in=Reserva.STATUS_ATIVOS,
            data_hora__gt=timezone.now(),
        )

    def get(self, request, *args, **kwargs):
        return render(request, self.template_name, {"reserva": self.get_reserva()})

    def post(self, request, *args, **kwargs):
        reserva = self.get_reserva()
        reserva.status = Reserva.Status.CANCELADA
        reserva.save(update_fields=["status"])
        messages.info(request, "Reserva cancelada.")
        return redirect("pedidos:reservas")
