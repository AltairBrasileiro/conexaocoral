from __future__ import annotations

from rest_framework import serializers

from core.models import Consulado, FotoConsulado, MembroConsulado
from core.serializers.base import UsuarioResumoSerializer, ValidacaoServiceMixin
from core.services import ConsuladoService


class FotoConsuladoSerializer(serializers.ModelSerializer):
    class Meta:
        model = FotoConsulado
        fields = ("id", "url", "legenda")
        read_only_fields = fields


class ConsuladoSerializer(ValidacaoServiceMixin, serializers.ModelSerializer):
    responsavel = UsuarioResumoSerializer(read_only=True)
    fotos = FotoConsuladoSerializer(many=True, read_only=True)
    # Valores anotados pelo repositório (fallback seguro quando não anotados, ex.: após create).
    total_membros = serializers.SerializerMethodField()
    eh_membro = serializers.SerializerMethodField()

    class Meta:
        model = Consulado
        fields = (
            "id", "nome", "descricao", "endereco", "latitude", "longitude", "link_whatsapp", "logo_url",
            "status_aprovacao", "responsavel", "fotos", "total_membros", "eh_membro", "criado_em",
        )
        read_only_fields = ("id", "status_aprovacao", "criado_em")

    def get_total_membros(self, obj: Consulado) -> int:
        valor = getattr(obj, "total_membros", None)
        return valor if valor is not None else obj.filiacoes.count()

    def get_eh_membro(self, obj: Consulado) -> bool:
        valor = getattr(obj, "eh_membro", None)
        if valor is not None:
            return bool(valor)
        return obj.filiacoes.filter(usuario=self.usuario_logado).exists()

    def validate(self, attrs: dict) -> dict:
        if self.instance is None:  # criação
            self.executar_validacao(ConsuladoService.validar_criacao, self.usuario_logado)
        return attrs


class MembroConsuladoSerializer(serializers.ModelSerializer):
    usuario = UsuarioResumoSerializer(read_only=True)

    class Meta:
        model = MembroConsulado
        fields = ("id", "usuario", "data_filiacao")
        read_only_fields = fields
