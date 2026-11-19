"""Cardápio público do site, com aviso de item esgotado (consulta o estoque)."""
from itertools import groupby

from django.db.models import Q
from django.views.generic import TemplateView

from ..models import CategoriaCardapio, ItemCardapio


class CardapioView(TemplateView):
    template_name = "pedidos/cardapio.html"

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        busca = self.request.GET.get("q", "").strip()
        categoria_id = self.request.GET.get("categoria", "")

        itens = (
            ItemCardapio.objects.filter(disponivel=True, categoria__ativa=True)
            .select_related("categoria")
            .prefetch_related("ficha_tecnica__insumo")
            .order_by("categoria__ordem", "categoria__nome", "-destaque", "nome")
        )
        if busca:
            itens = itens.filter(Q(nome__icontains=busca) | Q(descricao__icontains=busca))
        if categoria_id.isdigit():
            itens = itens.filter(categoria_id=int(categoria_id))

        itens = list(itens)
        for item in itens:
            # Esgotado = falta algum insumo da ficha técnica no estoque (app inventario).
            item.esgotado = not item.tem_estoque()

        contexto.update(
            {
                "grupos": [(categoria, list(lista)) for categoria, lista in groupby(itens, key=lambda i: i.categoria)],
                "categorias": CategoriaCardapio.objects.filter(ativa=True, itens__disponivel=True).distinct(),
                "busca": busca,
                "categoria_atual": int(categoria_id) if categoria_id.isdigit() else None,
                "total_itens": len(itens),
            }
        )
        return contexto