"""
Popula o banco com dados de exemplo para a apresentação.

Uso:  python manage.py popular_dados
Pode ser executado mais de uma vez: cadastros já existentes são reaproveitados
e as comandas de exemplo só são criadas se ainda não houver nenhuma.
"""
from datetime import timedelta
from decimal import Decimal as D

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from contas.models import Perfil
from inventario.models import CategoriaInsumo, Fornecedor, Insumo
from inventario.utils import registrar_entrada
from pedidos.models import (
    CategoriaCardapio,
    Comanda,
    FichaTecnica,
    ItemCardapio,
    ItemPedido,
    Mesa,
    Reserva,
)

SENHA_PADRAO = "senha123"

USUARIOS = [
    # username, nome, sobrenome, tipo
    ("gerente", "Marina", "Souza", Perfil.Tipo.GERENTE),
    ("garcom1", "Carlos", "Lima", Perfil.Tipo.GARCOM),
    ("garcom2", "Beatriz", "Rocha", Perfil.Tipo.GARCOM),
    ("cozinha", "Rafael", "Teixeira", Perfil.Tipo.COZINHA),
    ("cliente1", "Ana", "Pereira", Perfil.Tipo.CLIENTE),
    ("cliente2", "Diego", "Martins", Perfil.Tipo.CLIENTE),
]

FORNECEDORES = [
    ("Distribuidora Gelada", "12.345.678/0001-90", "Paulo", "(35) 3821-1000"),
    ("Hortifruti Lavras", "23.456.789/0001-01", "Lúcia", "(35) 3822-2000"),
    ("Frigorífico Sul de Minas", "34.567.890/0001-12", "Jorge", "(35) 3823-3000"),
    ("Atacadão Mercearia", "45.678.901/0001-23", "Sônia", "(35) 3824-4000"),
]

CATEGORIAS_INSUMO = [
    "Cervejas", "Destilados", "Não alcoólicos", "Carnes", "Hortifruti",
    "Laticínios", "Mercearia", "Congelados", "Padaria",
]

UN, KG, L = Insumo.Unidade.UNIDADE, Insumo.Unidade.QUILO, Insumo.Unidade.LITRO

# Bebidas: categorias Cervejas, Destilados e Não alcoólicos; o resto são ingredientes.
# nome, categoria, unidade, estoque, mínimo, custo, fornecedor, validade (dias a partir de hoje)
INSUMOS = [
    ("Cerveja Pilsen long neck 355 ml", "Cervejas", UN, "120", "48", "4.50", "Distribuidora Gelada", None),
    ("Cerveja IPA lata 473 ml", "Cervejas", UN, "30", "24", "9.90", "Distribuidora Gelada", None),
    ("Refrigerante cola lata 350 ml", "Não alcoólicos", UN, "60", "24", "3.20", "Distribuidora Gelada", None),
    ("Água mineral 500 ml", "Não alcoólicos", UN, "18", "24", "1.50", "Distribuidora Gelada", None),
    ("Água tônica lata 350 ml", "Não alcoólicos", UN, "36", "24", "3.50", "Distribuidora Gelada", None),
    ("Suco de laranja natural", "Não alcoólicos", L, "8", "5", "6.00", "Hortifruti Lavras", 3),
    ("Cachaça artesanal", "Destilados", L, "4", "2", "45.00", "Distribuidora Gelada", None),
    ("Gin", "Destilados", L, "1.5", "2", "90.00", "Distribuidora Gelada", None),
    ("Batata pré-frita congelada", "Congelados", KG, "25", "10", "14.00", "Atacadão Mercearia", 90),
    ("Mandioca descascada", "Hortifruti", KG, "10", "5", "6.00", "Hortifruti Lavras", 5),
    ("Óleo de soja", "Mercearia", L, "18", "6", "8.00", "Atacadão Mercearia", 180),
    ("Picanha", "Carnes", KG, "12", "5", "89.00", "Frigorífico Sul de Minas", 5),
    ("Filé de frango", "Carnes", KG, "15", "6", "22.00", "Frigorífico Sul de Minas", 4),
    ("Blend bovino 150 g", "Carnes", UN, "30", "20", "7.50", "Frigorífico Sul de Minas", 10),
    ("Pão de hambúrguer", "Padaria", UN, "40", "30", "1.20", "Atacadão Mercearia", 6),
    ("Queijo muçarela", "Laticínios", KG, "3", "4", "42.00", "Atacadão Mercearia", 15),
    ("Alface", "Hortifruti", UN, "0", "5", "3.00", "Hortifruti Lavras", None),
    ("Tomate", "Hortifruti", KG, "5", "3", "7.00", "Hortifruti Lavras", -1),
    ("Limão taiti", "Hortifruti", KG, "6", "2", "5.00", "Hortifruti Lavras", 12),
    ("Açúcar", "Mercearia", KG, "10", "3", "4.50", "Atacadão Mercearia", 365),
    ("Sorvete de creme", "Laticínios", L, "6", "3", "25.00", "Atacadão Mercearia", 60),
    ("Chocolate meio amargo", "Mercearia", KG, "2", "1", "55.00", "Atacadão Mercearia", 120),
]

CATEGORIAS_CARDAPIO = [
    ("Petiscos", 1), ("Pratos", 2), ("Lanches", 3), ("Bebidas", 4), ("Drinks", 5), ("Sobremesas", 6),
]

# nome, categoria, preço, tempo (min), destaque, ficha técnica [(insumo, quantidade)]
CARDAPIO = [
    ("Batata frita", "Petiscos", "32.90", 15, True,
     [("Batata pré-frita congelada", "0.400"), ("Óleo de soja", "0.050")]),
    ("Mandioca frita", "Petiscos", "29.90", 15, False,
     [("Mandioca descascada", "0.500"), ("Óleo de soja", "0.050")]),
    ("Frango a passarinho", "Petiscos", "44.90", 20, False,
     [("Filé de frango", "0.500"), ("Óleo de soja", "0.080"), ("Limão taiti", "0.050")]),
    ("Picanha na chapa", "Pratos", "89.90", 25, True,
     [("Picanha", "0.400"), ("Óleo de soja", "0.020")]),
    ("Filé de frango com fritas", "Pratos", "42.90", 25, False,
     [("Filé de frango", "0.250"), ("Batata pré-frita congelada", "0.200"), ("Óleo de soja", "0.030")]),
    ("X-Burger", "Lanches", "28.90", 15, False,
     [("Pão de hambúrguer", "1"), ("Blend bovino 150 g", "1"), ("Queijo muçarela", "0.040")]),
    ("X-Salada", "Lanches", "31.90", 15, False,
     [("Pão de hambúrguer", "1"), ("Blend bovino 150 g", "1"), ("Queijo muçarela", "0.040"),
      ("Alface", "0.100"), ("Tomate", "0.050")]),
    ("Cerveja Pilsen long neck", "Bebidas", "11.90", 0, False,
     [("Cerveja Pilsen long neck 355 ml", "1")]),
    ("Cerveja IPA 473 ml", "Bebidas", "22.90", 0, False, [("Cerveja IPA lata 473 ml", "1")]),
    ("Refrigerante lata", "Bebidas", "7.50", 0, False, [("Refrigerante cola lata 350 ml", "1")]),
    ("Água mineral", "Bebidas", "5.00", 0, False, [("Água mineral 500 ml", "1")]),
    ("Suco de laranja 400 ml", "Bebidas", "12.90", 5, False, [("Suco de laranja natural", "0.400")]),
    ("Caipirinha de limão", "Drinks", "24.90", 8, True,
     [("Cachaça artesanal", "0.060"), ("Limão taiti", "0.120"), ("Açúcar", "0.030")]),
    ("Gin tônica", "Drinks", "34.90", 5, False,
     [("Gin", "0.060"), ("Água tônica lata 350 ml", "1"), ("Limão taiti", "0.020")]),
    ("Petit gâteau", "Sobremesas", "29.90", 12, False,
     [("Chocolate meio amargo", "0.080"), ("Sorvete de creme", "0.100")]),
]

# número, capacidade, área
MESAS = [
    (1, 4, Mesa.Area.SALAO), (2, 4, Mesa.Area.SALAO), (3, 2, Mesa.Area.SALAO),
    (4, 6, Mesa.Area.SALAO), (5, 4, Mesa.Area.VARANDA), (6, 4, Mesa.Area.VARANDA),
    (7, 2, Mesa.Area.VARANDA), (8, 8, Mesa.Area.EXTERNA), (9, 4, Mesa.Area.EXTERNA),
    (10, 1, Mesa.Area.BALCAO), (11, 1, Mesa.Area.BALCAO), (12, 6, Mesa.Area.EXTERNA),
]


class Command(BaseCommand):
    help = "Cria perfis, usuários, estoque, cardápio, mesas, comandas e reservas de exemplo."

    @transaction.atomic
    def handle(self, *args, **options):
        call_command("configurar_perfis", stdout=self.stdout)
        usuarios = self.criar_usuarios()
        self.criar_estoque(usuarios["gerente"])
        self.criar_cardapio()
        mesas = self.criar_mesas()
        self.criar_comandas(usuarios, mesas)
        self.criar_reservas(usuarios, mesas)
        self.stdout.write(self.style.SUCCESS(
            f"Dados de exemplo prontos. Usuários de teste usam a senha '{SENHA_PADRAO}'."
        ))

    # ------------------------------------------------------------------
    def criar_usuarios(self):
        Usuario = get_user_model()
        usuarios = {}
        for username, nome, sobrenome, tipo in USUARIOS:
            usuario, criado = Usuario.objects.get_or_create(
                username=username,
                defaults={
                    "first_name": nome,
                    "last_name": sobrenome,
                    "email": f"{username}@gestorbar.local",
                },
            )
            if criado:
                usuario.set_password(SENHA_PADRAO)
                usuario.save()
            perfil, _ = Perfil.objects.get_or_create(usuario=usuario)
            if perfil.tipo != tipo:
                perfil.tipo = tipo
            perfil.save()  # garante grupo e acesso ao admin
            usuario.refresh_from_db()
            usuarios[username] = usuario
        self.stdout.write(f"- {len(usuarios)} usuários")
        return usuarios

    def criar_estoque(self, gerente):
        fornecedores = {}
        for nome, cnpj, contato, telefone in FORNECEDORES:
            fornecedores[nome], _ = Fornecedor.objects.get_or_create(
                nome=nome, defaults={"cnpj": cnpj, "contato": contato, "telefone": telefone}
            )
        categorias = {
            nome: CategoriaInsumo.objects.get_or_create(nome=nome)[0] for nome in CATEGORIAS_INSUMO
        }
        hoje = timezone.localdate()
        novos = 0
        for nome, categoria, unidade, estoque, minimo, custo, fornecedor, validade in INSUMOS:
            insumo, criado = Insumo.objects.get_or_create(
                nome=nome,
                defaults={
                    "categoria": categorias[categoria],
                    "unidade": unidade,
                    "estoque_minimo": D(minimo),
                    "custo_unitario": D(custo),
                    "fornecedor": fornecedores[fornecedor],
                    "validade": hoje + timedelta(days=validade) if validade is not None else None,
                },
            )
            if criado and D(estoque) > 0:
                # O saldo inicial entra como movimentação (função do app inventario).
                registrar_entrada(
                    insumo,
                    D(estoque),
                    custo_unitario=D(custo),
                    usuario=gerente,
                    observacao="Estoque inicial",
                )
            novos += criado
        self.stdout.write(f"- {len(FORNECEDORES)} fornecedores, {len(INSUMOS)} insumos ({novos} novos)")

    def criar_cardapio(self):
        categorias = {
            nome: CategoriaCardapio.objects.get_or_create(nome=nome, defaults={"ordem": ordem})[0]
            for nome, ordem in CATEGORIAS_CARDAPIO
        }
        for nome, categoria, preco, tempo, destaque, ficha in CARDAPIO:
            item, criado = ItemCardapio.objects.get_or_create(
                nome=nome,
                defaults={
                    "categoria": categorias[categoria],
                    "preco": D(preco),
                    "tempo_preparo": tempo,
                    "destaque": destaque,
                },
            )
            if criado:
                for nome_insumo, quantidade in ficha:
                    FichaTecnica.objects.create(
                        item=item, insumo=Insumo.objects.get(nome=nome_insumo), quantidade=D(quantidade)
                    )
        self.stdout.write(f"- {len(CARDAPIO)} itens no cardápio")

    def criar_mesas(self):
        mesas = {}
        for numero, capacidade, area in MESAS:
            mesas[numero], _ = Mesa.objects.get_or_create(
                numero=numero, defaults={"capacidade": capacidade, "area": area}
            )
        Mesa.objects.filter(numero=12).update(status=Mesa.Status.MANUTENCAO)
        self.stdout.write(f"- {len(mesas)} mesas")
        return mesas

    def criar_comandas(self, usuarios, mesas):
        if Comanda.objects.exists():
            self.stdout.write("- comandas já existem; nada a criar")
            return
        item = {i.nome: i for i in ItemCardapio.objects.all()}
        agora = timezone.now()
        gerente = usuarios["gerente"]

        def nova(mesa, garcom, itens, pessoas=2, cliente=None, nome="", horas_atras=1):
            comanda = Comanda.objects.create(
                mesa=mesas[mesa],
                garcom=usuarios[garcom],
                cliente=usuarios.get(cliente) if cliente else None,
                nome_cliente=nome,
                pessoas=pessoas,
                aberta_em=agora - timedelta(hours=horas_atras),
            )
            for nome_item, quantidade, status in itens:
                ItemPedido.objects.create(
                    comanda=comanda, item=item[nome_item], quantidade=quantidade, status=status
                )
            return comanda

        P, E, R, ENT = (
            ItemPedido.Status.PENDENTE,
            ItemPedido.Status.EM_PREPARO,
            ItemPedido.Status.PRONTO,
            ItemPedido.Status.ENTREGUE,
        )

        # Comandas já pagas (geram saída no estoque).
        fechadas = [
            (nova(1, "garcom1", [("Batata frita", 2, ENT), ("Cerveja Pilsen long neck", 4, ENT),
                                  ("Picanha na chapa", 1, ENT)], pessoas=4, nome="Família Andrade", horas_atras=5),
             Comanda.FormaPagamento.CREDITO),
            (nova(3, "garcom2", [("Caipirinha de limão", 2, ENT), ("Frango a passarinho", 1, ENT),
                                  ("Refrigerante lata", 2, ENT)], cliente="cliente1", horas_atras=4),
             Comanda.FormaPagamento.PIX),
            (nova(5, "garcom1", [("X-Burger", 2, ENT), ("Suco de laranja 400 ml", 2, ENT),
                                  ("Petit gâteau", 1, ENT)], nome="Mesa da varanda", horas_atras=3),
             Comanda.FormaPagamento.DEBITO),
        ]
        for comanda, forma in fechadas:
            comanda.fechar(forma_pagamento=forma, usuario=gerente)

        # Comandas em andamento.
        nova(2, "garcom1", [("Cerveja Pilsen long neck", 3, ENT), ("Mandioca frita", 1, E)],
             pessoas=3, nome="Grupo do futebol")
        nova(4, "garcom2", [("Gin tônica", 2, R), ("Batata frita", 1, P)], cliente="cliente2", pessoas=2)
        nova(7, "garcom2", [("Filé de frango com fritas", 1, P), ("Água mineral", 1, ENT)], pessoas=1)
        self.stdout.write("- 6 comandas (3 fechadas, 3 abertas)")

    def criar_reservas(self, usuarios, mesas):
        if Reserva.objects.exists():
            return
        amanha = timezone.localtime() + timedelta(days=1)
        horario = amanha.replace(hour=20, minute=0, second=0, microsecond=0)
        Reserva.objects.create(
            cliente=usuarios["cliente1"], mesa=mesas[8], data_hora=horario, pessoas=6,
            status=Reserva.Status.CONFIRMADA, observacao="Aniversário",
        )
        Reserva.objects.create(
            cliente=usuarios["cliente2"], data_hora=horario + timedelta(days=1, hours=1), pessoas=2,
        )
        Reserva.objects.create(
            cliente=usuarios["cliente1"], mesa=mesas[6], data_hora=horario - timedelta(days=3),
            pessoas=3, status=Reserva.Status.CONCLUIDA,
        )
        self.stdout.write("- 3 reservas")
