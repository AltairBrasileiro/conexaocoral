"""
Configurações do projeto Conexão Coral.

Todas as informações sensíveis (chaves, credenciais de banco) são lidas de
variáveis de ambiente via ``python-decouple``. Veja ``.env.example``.
"""
from datetime import timedelta
from pathlib import Path

from decouple import Csv, config

# ---------------------------------------------------------------------------
# Caminhos
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# Segurança
# ---------------------------------------------------------------------------
SECRET_KEY = config("DJANGO_SECRET_KEY")
DEBUG = config("DJANGO_DEBUG", default=False, cast=bool)
ALLOWED_HOSTS = config("DJANGO_ALLOWED_HOSTS", default="localhost,127.0.0.1", cast=Csv())

# ---------------------------------------------------------------------------
# Aplicações
# ---------------------------------------------------------------------------
DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

THIRD_PARTY_APPS = [
    "rest_framework",
    "rest_framework_simplejwt",
    "django_filters",
    "drf_spectacular",
    "corsheaders",
]

LOCAL_APPS = [
    "core.apps.CoreConfig",
    "web.apps.WebConfig",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    # Arquivos estáticos em produção sem depender de nginx (logo após o SecurityMiddleware).
    "whitenoise.middleware.WhiteNoiseMiddleware",
    # Deve vir antes de qualquer middleware que gere respostas (ex.: CommonMiddleware).
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "main.urls"
WSGI_APPLICATION = "main.wsgi.application"
ASGI_APPLICATION = "main.asgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
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

# ---------------------------------------------------------------------------
# Banco de dados - SQLite (testes/desenvolvimento) ou PostgreSQL (produção)
# ---------------------------------------------------------------------------
DB_ENGINE = config("DB_ENGINE", default="sqlite")

if DB_ENGINE == "sqlite":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / config("DB_NAME", default="db.sqlite3"),
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": config("DB_NAME", default="conexao_coral"),
            "USER": config("DB_USER", default="postgres"),
            "PASSWORD": config("DB_PASSWORD", default=""),
            "HOST": config("DB_HOST", default="localhost"),
            "PORT": config("DB_PORT", default=5432, cast=int),
            # Reaproveita conexões entre requisições (em segundos).
            "CONN_MAX_AGE": config("DB_CONN_MAX_AGE", default=60, cast=int),
            # Descarta conexões persistentes quebradas antes de usá-las.
            "CONN_HEALTH_CHECKS": True,
            "OPTIONS": {
                "connect_timeout": 10,
            },
        }
    }

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ---------------------------------------------------------------------------
# CORS - origens autorizadas a chamar a API pelo navegador (app Flutter Web)
# ---------------------------------------------------------------------------
# Em desenvolvimento, libera qualquer porta de localhost (o "flutter run -d chrome"
# sobe em porta aleatória). Em produção, liste as origens em CORS_ALLOWED_ORIGINS.
CORS_ALLOWED_ORIGINS = config("CORS_ALLOWED_ORIGINS", default="", cast=Csv())
if DEBUG:
    CORS_ALLOWED_ORIGIN_REGEXES = [r"^http://(localhost|127\.0\.0\.1)(:\d+)?$"]

# ---------------------------------------------------------------------------
# Autenticação
# ---------------------------------------------------------------------------
AUTH_USER_MODEL = "core.Usuario"

# Interface web (app "web"): login por sessão, separado do JWT da API.
LOGIN_URL = "web:login"
LOGIN_REDIRECT_URL = "web:consulados"
LOGOUT_REDIRECT_URL = "web:login"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 8}},
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
STATIC_ROOT = BASE_DIR / "staticfiles"  # preenchido por "python manage.py collectstatic"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedStaticFilesStorage"},
}

# Imagens (fotos e logos dos consulados). Com SERVIR_MEDIA=True o próprio Django
# as entrega (ver main/urls.py) — bom para começar; com tráfego maior, sirva
# MEDIA_ROOT pelo nginx/CDN e desligue a opção.
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"
SERVIR_MEDIA = config("SERVIR_MEDIA", default=DEBUG, cast=bool)

# ---------------------------------------------------------------------------
# Django REST Framework
# ---------------------------------------------------------------------------
REST_FRAMEWORK = {
    # Autenticação JWT que, além da assinatura, exige o token na whitelist.
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "core.authentication.WhitelistJWTAuthentication",
    ),
    # Seguro por padrão: tudo exige login, exceto o que for liberado explicitamente.
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
    ),
    "DEFAULT_FILTER_BACKENDS": (
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ),
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "EXCEPTION_HANDLER": "core.views.exception_handler.custom_exception_handler",
    "DEFAULT_THROTTLE_CLASSES": (
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
        "rest_framework.throttling.ScopedRateThrottle",
    ),
    "DEFAULT_THROTTLE_RATES": {
        "anon": "60/minute",
        "user": "600/minute",
        "auth": "10/minute",  # login, registro e refresh
    },
    "DATETIME_FORMAT": "iso-8601",
}

# ---------------------------------------------------------------------------
# Simple JWT - tokens de 8 horas controlados por whitelist
# ---------------------------------------------------------------------------
# Como funciona a whitelist:
#   * Todo token emitido (access e refresh) tem seu "jti" gravado na tabela
#     ``TokenWhitelist``.
#   * A cada requisição, ``WhitelistJWTAuthentication`` valida a assinatura E
#     verifica se o jti ainda está na whitelist.
#   * Logout remove o jti da whitelist, invalidando o token imediatamente,
#     mesmo que ele ainda não tenha expirado.
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(hours=config("JWT_ACCESS_TOKEN_HOURS", default=8, cast=int)),
    "REFRESH_TOKEN_LIFETIME": timedelta(hours=config("JWT_REFRESH_TOKEN_HOURS", default=24, cast=int)),
    # Cada refresh gera um novo refresh token; o antigo sai da whitelist.
    "ROTATE_REFRESH_TOKENS": True,
    # A blacklist nativa do simplejwt não é usada: o controle é feito pela whitelist.
    "BLACKLIST_AFTER_ROTATION": False,
    "UPDATE_LAST_LOGIN": True,
    "ALGORITHM": "HS256",
    "SIGNING_KEY": config("JWT_SIGNING_KEY", default=SECRET_KEY),
    "AUTH_HEADER_TYPES": ("Bearer",),
    "AUTH_HEADER_NAME": "HTTP_AUTHORIZATION",
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
    "JTI_CLAIM": "jti",
    "TOKEN_TYPE_CLAIM": "token_type",
    "AUTH_TOKEN_CLASSES": ("rest_framework_simplejwt.tokens.AccessToken",),
    "TOKEN_OBTAIN_SERIALIZER": "core.serializers.auth.LoginSerializer",
    "TOKEN_REFRESH_SERIALIZER": "core.serializers.auth.WhitelistTokenRefreshSerializer",
}

# ---------------------------------------------------------------------------
# Documentação da API (drf-spectacular)
# ---------------------------------------------------------------------------
SPECTACULAR_SETTINGS = {
    "TITLE": "Conexão Coral API",
    "DESCRIPTION": "API REST de consulados, partidas, check-ins, eventos e aliados.",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
}

# ---------------------------------------------------------------------------
# Regras de negócio configuráveis
# ---------------------------------------------------------------------------
CONEXAO_CORAL = {
    # Janela em que o check-in é aceito, relativa ao horário da partida.
    # Use 0 em ambos para desativar a restrição de janela.
    "CHECKIN_HORAS_ANTES": config("CHECKIN_HORAS_ANTES", default=3, cast=int),
    "CHECKIN_HORAS_DEPOIS": config("CHECKIN_HORAS_DEPOIS", default=3, cast=int),
}

# ---------------------------------------------------------------------------
# Hardening para produção
# ---------------------------------------------------------------------------
# Origens HTTPS aceitas em formulários (login do /admin/ atrás de proxy).
# Ex.: CSRF_TRUSTED_ORIGINS=https://conexaocoral.com.br,https://www.conexaocoral.com.br
CSRF_TRUSTED_ORIGINS = config("CSRF_TRUSTED_ORIGINS", default="", cast=Csv())

if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 60 * 60 * 24 * 30
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_CONTENT_TYPE_NOSNIFF = True

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "padrao": {"format": "[{asctime}] {levelname} {name}: {message}", "style": "{"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "padrao"},
    },
    "loggers": {
        "core": {"handlers": ["console"], "level": "INFO", "propagate": False},
    },
}
