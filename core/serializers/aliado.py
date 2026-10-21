from __future__ import annotations

from rest_framework import serializers

from core.models import Aliado
from core.serializers.base import UsuarioResumoSerializer, ValidacaoServiceMixin
from core.services import AliadoService


class AliadoSerializer(ValidacaoServiceMixin, serializers.ModelSerializer):
    usuario = UsuarioResumoSerializer(read_only=True)
    categoria_display = serializers.CharField(source="get_categoria_display", read_only=True)

    class Meta:
        model = Aliado
        fields = (
            "id", "usuario", "nome_negocio", "categoria", "categoria_display", "descricao",
            "link_instagram", "link_whatsapp", "status_aprovacao", "selo_verificado", "criado_em",
        )
        # Moderação e selo só mudam pelas actions exclusivas do admin.
        read_only_fields = ("id", "status_aprovacao", "selo_verificado", "criado_em")

    def validate(self, attrs: dict) -> dict:
        if self.instance is None:
            self.executar_validacao(AliadoService.validar_criacao, self.usuario_logado)
        return attrs
