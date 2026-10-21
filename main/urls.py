"""
Rotas do projeto Conexão Coral.

Todas as rotas da API ficam sob ``/api/v1/``:

    auth/registro/                POST   cadastro público
    auth/login/                   POST   login (access 8h + refresh)
    auth/refresh/                 POST   renova tokens (rotação + whitelist)
    auth/logout/                  POST   revoga sessão atual
    auth/logout-todos/            POST   revoga todas as sessões do usuário

    usuarios/ | usuarios/me/
    consulados/ | {id}/aprovar | {id}/rejeitar | {id}/membros | {id}/sair
    partidas/ | proximas/ | {id}/ranking-consulados/
    checkins/ | {id}/cancelar/
    eventos/ | {id}/aprovar | {id}/rejeitar | {id}/presencas
    presencas-evento/
    aliados/ | {id}/aprovar | {id}/rejeitar | {id}/conceder-selo | {id}/revogar-selo

Documentação interativa: /api/docs/ (Swagger) e /api/redoc/.

A interface web (páginas HTML renderizadas pelo Django) fica na raiz "/";
as rotas estão em ``web/urls.py``.
"""
from django.conf import settings
from django.contrib import admin
from django.urls import include, path, re_path
from django.views.static import serve
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView
from rest_framework.routers import DefaultRouter

from core.views import (
    AliadoViewSet,
    CheckInViewSet,
    ConsuladoViewSet,
    EventoViewSet,
    LoginView,
    LogoutTodosView,
    LogoutView,
    PartidaViewSet,
    PresencaEventoViewSet,
    RefreshView,
    RegistroView,
    UsuarioViewSet,
)

# ---------------------------------------------------------------------------
# Router do DRF (gera as rotas CRUD + actions dos ViewSets)
# ---------------------------------------------------------------------------
router = DefaultRouter()
router.register("usuarios", UsuarioViewSet, basename="usuario")
router.register("consulados", ConsuladoViewSet, basename="consulado")
router.register("partidas", PartidaViewSet, basename="partida")
router.register("checkins", CheckInViewSet, basename="checkin")
router.register("eventos", EventoViewSet, basename="evento")
router.register("presencas-evento", PresencaEventoViewSet, basename="presenca-evento")
router.register("aliados", AliadoViewSet, basename="aliado")

# ---------------------------------------------------------------------------
# Autenticação JWT (whitelist)
# ---------------------------------------------------------------------------
auth_urlpatterns = [
    path("registro/", RegistroView.as_view(), name="auth-registro"),
    path("login/", LoginView.as_view(), name="auth-login"),
    path("refresh/", RefreshView.as_view(), name="auth-refresh"),
    path("logout/", LogoutView.as_view(), name="auth-logout"),
    path("logout-todos/", LogoutTodosView.as_view(), name="auth-logout-todos"),
]

api_v1_urlpatterns = [
    path("auth/", include(auth_urlpatterns)),
    path("", include(router.urls)),
]

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/", include(api_v1_urlpatterns)),
    # Documentação OpenAPI
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
    # Interface web (templates Django) — ver web/urls.py.
    path("", include("web.urls")),
]

if settings.SERVIR_MEDIA:
    # Fotos e logos dos consulados. Passa pelos middlewares (inclusive CORS), então o
    # app Flutter Web também consegue carregá-las. Ver SERVIR_MEDIA em settings.py.
    urlpatterns += [
        re_path(rf"^{settings.MEDIA_URL.strip('/')}/(?P<path>.*)$", serve, {"document_root": settings.MEDIA_ROOT}),
    ]
