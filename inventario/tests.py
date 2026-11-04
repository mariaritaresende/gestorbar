from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import (
    CategoriaInsumo,
    EstoqueInsuficiente,
    Fornecedor,
    Insumo,
    MovimentacaoEstoque,
)
from .utils import (
    baixar_estoque,
    lista_de_compras,
    registrar_entrada,
    registrar_saida,
    verificar_disponibilidade,
)


class BaseInventarioTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.bebidas = CategoriaInsumo.objects.create(nome="Bebidas")
        cls.fornecedor = Fornecedor.objects.create(nome="Distribuidora Lavras")
        cls.cerveja = Insumo.objects.create(
            nome="Cerveja long neck", categoria=cls.bebidas, fornecedor=cls.fornecedor,
            unidade=Insumo.Unidade.UNIDADE, estoque_minimo=Decimal("24"),
        )
        cls.limao = Insumo.objects.create(
            nome="Limão", categoria=cls.bebidas, unidade=Insumo.Unidade.QUILO,
            estoque_minimo=Decimal("2"),
        )

    def recarregar(self, insumo):
        insumo.refresh_from_db()
        return insumo


class MovimentacaoTests(BaseInventarioTestCase):
    def test_entrada_aumenta_estoque_e_registra_saldo(self):
        mov = registrar_entrada(self.cerveja, 48, custo_unitario=Decimal("4.50"))
        self.assertEqual(self.recarregar(self.cerveja).quantidade_estoque, Decimal("48"))
        self.assertEqual(mov.saldo_apos, Decimal("48"))

    def test_saida_diminui_estoque(self):
        registrar_entrada(self.cerveja, 48)
        registrar_saida(self.cerveja, 10)
        self.assertEqual(self.recarregar(self.cerveja).quantidade_estoque, Decimal("38"))

    def test_saida_maior_que_saldo_e_recusada(self):
        registrar_entrada(self.cerveja, 5)
        with self.assertRaises(EstoqueInsuficiente):
            registrar_saida(self.cerveja, 6)
        self.assertEqual(self.recarregar(self.cerveja).quantidade_estoque, Decimal("5"))
        self.assertEqual(self.cerveja.movimentacoes.count(), 1)

    def test_custo_medio_ponderado(self):
        registrar_entrada(self.cerveja, 10, custo_unitario=Decimal("4.00"))
        registrar_entrada(self.cerveja, 10, custo_unitario=Decimal("6.00"))
        self.assertEqual(self.recarregar(self.cerveja).custo_unitario, Decimal("5.00"))

    def test_entrada_atualiza_validade(self):
        validade = timezone.localdate() + timedelta(days=60)
        registrar_entrada(self.limao, 3, validade=validade)
        self.assertEqual(self.recarregar(self.limao).validade, validade)

    def test_movimentacao_e_imutavel(self):
        mov = registrar_entrada(self.cerveja, 5)
        mov.quantidade = Decimal("50")
        with self.assertRaises(ValidationError):
            mov.save()
        with self.assertRaises(ValidationError):
            mov.delete()

    def test_clean_mostra_erro_de_estoque_no_formulario(self):
        mov = MovimentacaoEstoque(
            insumo=self.cerveja, tipo=MovimentacaoEstoque.Tipo.PERDA, quantidade=Decimal("1")
        )
        with self.assertRaises(ValidationError):
            mov.full_clean()


class BaixaEmLoteTests(BaseInventarioTestCase):
    def test_baixa_todos_os_insumos(self):
        registrar_entrada(self.cerveja, 10)
        registrar_entrada(self.limao, Decimal("1.5"))
        movs = baixar_estoque({self.cerveja: 2, self.limao: Decimal("0.300")}, observacao="Comanda 1")
        self.assertEqual(len(movs), 2)
        self.assertEqual(self.recarregar(self.cerveja).quantidade_estoque, Decimal("8"))
        self.assertEqual(self.recarregar(self.limao).quantidade_estoque, Decimal("1.2"))

    def test_soma_insumos_repetidos(self):
        registrar_entrada(self.cerveja, 10)
        baixar_estoque([(self.cerveja, 3), (self.cerveja, 4)])
        self.assertEqual(self.recarregar(self.cerveja).quantidade_estoque, Decimal("3"))

    def test_tudo_ou_nada_quando_falta_um_insumo(self):
        registrar_entrada(self.cerveja, 10)  # limão está zerado
        with self.assertRaises(EstoqueInsuficiente) as ctx:
            baixar_estoque({self.cerveja: 2, self.limao: 1})
        self.assertEqual([f[0] for f in ctx.exception.faltas], [self.limao])
        self.assertEqual(self.recarregar(self.cerveja).quantidade_estoque, Decimal("10"))

    def test_verificar_disponibilidade(self):
        registrar_entrada(self.cerveja, 1)
        faltas = verificar_disponibilidade({self.cerveja: 2})
        self.assertEqual(faltas[0][0], self.cerveja)


class ConsultasTests(BaseInventarioTestCase):
    def test_situacao_do_estoque(self):
        registrar_entrada(self.cerveja, 30)   # acima do mínimo (24)
        registrar_entrada(self.limao, 1)      # abaixo do mínimo (2)
        self.assertIn(self.cerveja, Insumo.objects.estoque_ok())
        self.assertIn(self.limao, Insumo.objects.abaixo_do_minimo())
        self.assertEqual(self.recarregar(self.limao).situacao_estoque, Insumo.Situacao.BAIXO)

    def test_vencidos_e_vencendo(self):
        hoje = timezone.localdate()
        Insumo.objects.filter(pk=self.cerveja.pk).update(validade=hoje - timedelta(days=1))
        Insumo.objects.filter(pk=self.limao.pk).update(validade=hoje + timedelta(days=3))
        self.assertEqual(list(Insumo.objects.vencidos()), [self.cerveja])
        self.assertEqual(list(Insumo.objects.vencendo()), [self.limao])

    def test_lista_de_compras(self):
        registrar_entrada(self.limao, 1)
        sugestoes = dict(lista_de_compras())
        self.assertEqual(sugestoes[self.limao], Decimal("3"))  # 2×2 − 1


class AdminInventarioTests(BaseInventarioTestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_superuser("admin", "a@a.com", "senha123")
        self.client.force_login(self.admin)

    def test_listagens_e_filtros_abrem(self):
        url = reverse("admin:inventario_insumo_changelist")
        for params in ("", "?situacao=ZERADO", "?situacao=BAIXO", "?situacao=OK",
                       "?validade_status=vencido", "?validade_status=7dias",
                       "?validade_status=sem"):
            self.assertEqual(self.client.get(url + params).status_code, 200, params)
        for nome in ("movimentacaoestoque", "fornecedor", "categoriainsumo"):
            url = reverse(f"admin:inventario_{nome}_changelist")
            self.assertEqual(self.client.get(url).status_code, 200)
        url = reverse("admin:inventario_movimentacaoestoque_changelist") + "?periodo=7"
        self.assertEqual(self.client.get(url).status_code, 200)

    def test_cadastro_de_movimentacao_pelo_admin(self):
        url = reverse("admin:inventario_movimentacaoestoque_add")
        resposta = self.client.post(url, {
            "insumo": self.cerveja.pk, "tipo": "ENTRADA", "quantidade": "12",
            "observacao": "Compra semanal",
        })
        self.assertEqual(resposta.status_code, 302)
        mov = MovimentacaoEstoque.objects.get()
        self.assertEqual(mov.usuario, self.admin)
        self.assertEqual(self.recarregar(self.cerveja).quantidade_estoque, Decimal("12"))

    def test_admin_recusa_saida_sem_estoque(self):
        url = reverse("admin:inventario_movimentacaoestoque_add")
        resposta = self.client.post(url, {
            "insumo": self.cerveja.pk, "tipo": "SAIDA", "quantidade": "1",
        })
        self.assertEqual(resposta.status_code, 200)  # volta ao formulário com erro
        self.assertContains(resposta, "Estoque insuficiente")
        self.assertFalse(MovimentacaoEstoque.objects.exists())

    def test_acao_baixar_vencidos(self):
        registrar_entrada(self.limao, 2)
        Insumo.objects.filter(pk=self.limao.pk).update(
            validade=timezone.localdate() - timedelta(days=1)
        )
        url = reverse("admin:inventario_insumo_changelist")
        self.client.post(url, {
            "action": "baixar_vencidos_como_perda", "_selected_action": [self.limao.pk],
        })
        self.assertEqual(self.recarregar(self.limao).quantidade_estoque, Decimal("0"))
        self.assertTrue(self.limao.movimentacoes.filter(tipo="PERDA").exists())