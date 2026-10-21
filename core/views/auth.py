"""Endpoints de autenticação: registro, login, refresh e logout (whitelist)."""
from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework import generics, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.settings import api_settings
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from core.serializers import (
    LoginSerializer,
    LogoutSerializer,
    RegistroSerializer,
    UsuarioSerializer,
    WhitelistTokenRefreshSerializer,
)
from core.services import TokenWhitelistService, UsuarioService


class RegistroView(generics.CreateAPIView):
    """POST /auth/registro/ — cadastro público de usuários."""

    serializer_class = RegistroSerializer
    permission_classes = (AllowAny,)
    authentication_classes = ()
    throttle_scope = "auth"

    def create(self, request: Request, *args, **kwargs) -> Response:
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        usuario = UsuarioService().registrar(**serializer.validated_data)
        return Response(UsuarioSerializer(usuario).data, status=status.HTTP_201_CREATED)


class LoginView(TokenObtainPairView):
    """POST /auth/login/ — devolve access (8h) + refresh e registra ambos na whitelist."""

    serializer_class = LoginSerializer
    throttle_scope = "auth"

    def post(self, request: Request, *args, **kwargs) -> Response:
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        dados = serializer.validated_data
        TokenWhitelistService().registrar_par(refresh=dados["refresh"], access=dados["access"])
        return Response(dados, status=status.HTTP_200_OK)


class RefreshView(TokenRefreshView):
    """POST /auth/refresh/ — troca um refresh válido (da whitelist) por novos tokens."""

    serializer_class = WhitelistTokenRefreshSerializer
    throttle_scope = "auth"

    def post(self, request: Request, *args, **kwargs) -> Response:
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        dados = serializer.validated_data
        TokenWhitelistService().rotacionar(
            refresh_antigo_jti=serializer.refresh_antigo_jti,
            access=dados["access"],
            refresh=dados.get("refresh"),
        )
        return Response(dados, status=status.HTTP_200_OK)


class LogoutView(APIView):
    """POST /auth/logout/ — revoga o refresh informado e o access usado na requisição."""

    permission_classes = (IsAuthenticated,)

    @extend_schema(request=LogoutSerializer, responses={204: None})
    def post(self, request: Request) -> Response:
        serializer = LogoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        access_jti = request.auth.get(api_settings.JTI_CLAIM) if request.auth else None
        TokenWhitelistService().revogar(serializer.refresh_jti, access_jti)
        return Response(status=status.HTTP_204_NO_CONTENT)


class LogoutTodosView(APIView):
    """POST /auth/logout-todos/ — encerra todas as sessões do usuário (todos os dispositivos)."""

    permission_classes = (IsAuthenticated,)

    @extend_schema(request=None, responses={204: None})
    def post(self, request: Request) -> Response:
        TokenWhitelistService().revogar_todos(request.user.id)
        return Response(status=status.HTTP_204_NO_CONTENT)
