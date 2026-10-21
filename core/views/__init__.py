"""Camada HTTP: ViewSets e APIViews."""
from core.views.aliado import AliadoViewSet
from core.views.auth import LoginView, LogoutTodosView, LogoutView, RefreshView, RegistroView
from core.views.checkin import CheckInViewSet
from core.views.consulado import ConsuladoViewSet
from core.views.evento import EventoViewSet, PresencaEventoViewSet
from core.views.partida import PartidaViewSet
from core.views.usuario import UsuarioViewSet

__all__ = [
    "AliadoViewSet",
    "CheckInViewSet",
    "ConsuladoViewSet",
    "EventoViewSet",
    "LoginView",
    "LogoutTodosView",
    "LogoutView",
    "PartidaViewSet",
    "PresencaEventoViewSet",
    "RefreshView",
    "RegistroView",
    "UsuarioViewSet",
]
