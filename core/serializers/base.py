"""Utilidades compartilhadas pelos serializers."""
from __future__ import annotations

from typing import Any, Callable

from rest_framework import serializers
from rest_framework.settings import api_settings

from core.exceptions import RegraNegocioError
from core.models import Usuario


class ValidacaoServiceMixin:
    """
    Executa validações da camada de serviço dentro do ``validate()`` e
    converte ``RegraNegocioError`` em ``ValidationError`` (HTTP 400),
    mantendo o campo afetado na resposta.
    """

    @staticmethod
    def executar_validacao(funcao: Callable[..., Any], *args: Any, **kwargs: Any) -> None:
        try:
            funcao(*args, **kwargs)
        except RegraNegocioError as exc:
            campo = exc.campo or api_settings.NON_FIELD_ERRORS_KEY
            raise serializers.ValidationError({campo: [exc.mensagem]}, code=exc.codigo) from exc

    @property
    def usuario_logado(self) -> Usuario:
        return self.context["request"].user  # type: ignore[attr-defined]


class UsuarioResumoSerializer(serializers.ModelSerializer):
    """Representação enxuta de usuário para aninhar em outros recursos."""

    class Meta:
        model = Usuario
        fields = ("id", "nome")
        read_only_fields = fields
