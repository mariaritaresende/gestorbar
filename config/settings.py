"""
Configurações do projeto GestorBar — Sistema de Gestão para Bares e Restaurantes.
GAC116 - Programação Web (UFLA).
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# Segurança (valores de desenvolvimento; em produção, use variáveis de ambiente)
# ---------------------------------------------------------------------------
SECRET_KEY = os.environ.get(
    "DJANGO_SECRET_KEY",
    "django-insecure-gestorbar-troque-esta-chave-em-producao",
)
DEBUG = os.environ.get("DJANGO_DEBUG", "1") == "1"
ALLOWED_HOSTS = os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")

# ---------------------------------------------------------------------------
# Aplicações
# ---------------------------------------------------------------------------
INSTALLED_APPS = [
    # O Jazzmin precisa vir ANTES do django.contrib.admin para substituir o tema.
    "jazzmin",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Apps do projeto
    "contas.apps.ContasConfig",
    "inventario.apps.InventarioConfig",
    "pedidos.apps.PedidosConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        # Templates do projeto (inclui a personalização do painel admin).
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# ---------------------------------------------------------------------------
# Banco de dados relacional (SQLite em desenvolvimento)
# ---------------------------------------------------------------------------
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ---------------------------------------------------------------------------
# Internacionalização
# ---------------------------------------------------------------------------
LANGUAGE_CODE = "pt-br"
TIME_ZONE = "America/Sao_Paulo"
USE_I18N = True
USE_TZ = True

# ---------------------------------------------------------------------------
# Arquivos estáticos
# ---------------------------------------------------------------------------
STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGIN_URL = "admin:login"

# ---------------------------------------------------------------------------
# Tema do painel administrativo (Jazzmin)
# https://django-jazzmin.readthedocs.io/
# ---------------------------------------------------------------------------
JAZZMIN_SETTINGS = {
    "site_title": "GestorBar | Administração",
    "site_header": "GestorBar",
    "site_brand": "GestorBar",
    "site_logo": "img/gestorbar-logo.svg",
    "site_logo_classes": "img-circle",
    "site_icon": "img/gestorbar-logo.svg",
    "welcome_sign": "Use o usuário e a senha da equipe.",
    "copyright": "GestorBar · GAC116 UFLA",
    "search_model": ["pedidos.ItemCardapio", "inventario.Insumo"],
    "user_avatar": None,
    "topmenu_links": [
        {"name": "Painel", "url": "admin:index"},
        {"name": "Ver site", "url": "home", "new_window": True},
        {"model": "pedidos.Comanda"},
        {"model": "pedidos.ItemPedido"},
        {"model": "inventario.Insumo"},
    ],
    "usermenu_links": [
        {"name": "Ver site", "url": "home", "new_window": True, "icon": "fas fa-globe"},
    ],
    "show_sidebar": True,
    "navigation_expanded": True,
    "hide_models": [],
    "order_with_respect_to": [
        "pedidos",
        "pedidos.comanda",
        "pedidos.itempedido",
        "pedidos.mesa",
        "pedidos.reserva",
        "pedidos.itemcardapio",
        "pedidos.categoriacardapio",
        "inventario",
        "inventario.insumo",
        "inventario.movimentacaoestoque",
        "inventario.fornecedor",
        "inventario.categoriainsumo",
        "contas",
        "auth",
    ],
    "icons": {
        "auth": "fas fa-users-cog",
        "auth.user": "fas fa-user",
        "auth.group": "fas fa-users",
        "contas.perfil": "fas fa-id-badge",
        "pedidos.mesa": "fas fa-chair",
        "pedidos.comanda": "fas fa-receipt",
        "pedidos.itempedido": "fas fa-concierge-bell",
        "pedidos.itemcardapio": "fas fa-utensils",
        "pedidos.categoriacardapio": "fas fa-list",
        "pedidos.reserva": "fas fa-calendar-check",
        "inventario.insumo": "fas fa-boxes",
        "inventario.movimentacaoestoque": "fas fa-exchange-alt",
        "inventario.fornecedor": "fas fa-truck",
        "inventario.categoriainsumo": "fas fa-tags",
    },
    "default_icon_parents": "fas fa-folder",
    "default_icon_children": "fas fa-circle",
    "related_modal_active": True,
    "custom_css": "css/admin.css",
    # Botão de alternar tema claro/escuro no painel.
    "custom_js": "js/admin_tema.js",
    "show_ui_builder": False,
    "changeform_format": "horizontal_tabs",
    "changeform_format_overrides": {
        "auth.user": "collapsible",
        "auth.group": "vertical_tabs",
    },
    "language_chooser": False,
}

# "default_theme_mode": "auto" faz o admin seguir o tema claro/escuro do sistema
# operacional; o botão de static/js/admin_tema.js permite trocar manualmente.
JAZZMIN_UI_TWEAKS = {
    "theme": "flatly",
    "default_theme_mode": "auto",
    "navbar": "navbar-white navbar-light",
    "brand_colour": "navbar-warning",
    "accent": "accent-warning",
    "sidebar": "sidebar-dark-warning",
    "no_navbar_border": True,
    "navbar_fixed": True,
    "sidebar_fixed": True,
    "sidebar_nav_child_indent": True,
    "sidebar_nav_flat_style": True,
    "button_classes": {
        "primary": "btn-primary",
        "secondary": "btn-secondary",
        "info": "btn-info",
        "warning": "btn-warning",
        "danger": "btn-danger",
        "success": "btn-success",
    },
}
