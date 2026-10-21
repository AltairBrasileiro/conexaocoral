from __future__ import annotations

from typing import Any

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from core.models import TipoUsuario, Usuario
from core.serializers.base import ValidacaoServiceMixin
from core.services import UsuarioService


class UsuarioSerializer(serializers.ModelSerializer):
    """Perfil do próprio usuário (GET/PATCH em /usuarios/me/)."""

    class Meta:
        model = Usuario
        fields = ("id", "nome", "email", "telefone", "tipo_usuario", "criado_em")
        read_only_fields = ("id", "email", "tipo_usuario", "criado_em")


class UsuarioAdminSerializer(serializers.ModelSerializer):
    """Gestão de usuários pelo administrador (pode alterar papel e ativação)."""

    class Meta:
        model = Usuario
        fields = ("id", "nome", "email", "telefone", "tipo_usuario", "is_active", "last_login", "criado_em")
        read_only_fields = ("id", "email", "last_login", "criado_em")


class RegistroSerializer(ValidacaoServiceMixin, serializers.ModelSerializer):
    """Auto-cadastro público. O papel ADMIN não pode ser escolhido."""

    password = serializers.CharField(write_only=True, style={"input_type": "password"})
    password_confirmacao = serializers.CharField(write_only=True, style={"input_type": "password"})
    tipo_usuario = serializers.ChoiceField(
        choices=[c for c in TipoUsuario.choices if c[0] != TipoUsuario.ADMIN],
        default=TipoUsuario.TORCEDOR,
    )

    class Meta:
        model = Usuario
        fields = ("id", "nome", "email", "telefone", "tipo_usuario", "password", "password_confirmacao")
        read_only_fields = ("id",)
        # A unicidade (case-insensitive) é checada pelo serviço.
        extra_kwargs = {"email": {"validators": []}}

    def validate_email(self, valor: str) -> str:
        return valor.strip().lower()

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        if attrs["password"] != attrs.pop("password_confirmacao"):
            raise serializers.ValidationError({"password_confirmacao": ["As senhas não conferem."]})

        # Valida a senha contra os AUTH_PASSWORD_VALIDATORS usando os dados informados.
        usuario_provisorio = Usuario(email=attrs["email"], nome=attrs.get("nome", ""))
        try:
            validate_password(attrs["password"], user=usuario_provisorio)
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"password": list(exc.messages)}) from exc

        self.executar_validacao(
            UsuarioService().validar_registro, email=attrs["email"], tipo_usuario=attrs["tipo_usuario"],
        )
        return attrs
