from __future__ import annotations

from rest_framework import serializers

from core.models import Consulado, FotoConsulado, MembroConsulado, SolicitacaoMembro
from core.serializers.base import UsuarioResumoSerializer, ValidacaoServiceMixin
from core.services import ConsuladoService


class FotoConsuladoSerializer(serializers.ModelSerializer):
    # Arquivo enviado ou link externo, sempre como URL absoluta.
    url = serializers.SerializerMethodField()

    class Meta:
        model = FotoConsulado
        fields = ("id", "url", "legenda")
        read_only_fields = fields

    def get_url(self, obj: FotoConsulado) -> str:
        request = self.context.get("request")
        return request.build_absolute_uri(obj.src) if request and obj.imagem else obj.src


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
            "status_aprovacao", "motivo_rejeicao", "responsavel", "fotos", "total_membros", "eh_membro",
            "criado_em",
        )
        read_only_fields = ("id", "status_aprovacao", "motivo_rejeicao", "criado_em")

    def get_total_membros(self, obj: Consulado) -> int:
        valor = getattr(obj, "total_membros", None)
        return valor if valor is not None else obj.filiacoes.count()

    def get_eh_membro(self, obj: Consulado) -> bool:
        valor = getattr(obj, "eh_membro", None)
        if valor is not None:
            return bool(valor)
        return obj.filiacoes.filter(usuario=self.usuario_logado).exists()

    def to_representation(self, instance: Consulado) -> dict:
        dados = super().to_representation(instance)
        request = self.context.get("request")
        if request and not ConsuladoService().pode_ver_whatsapp(request.user, instance):
            dados["link_whatsapp"] = ""  # o grupo do WhatsApp é só para membros
        return dados

    def validate(self, attrs: dict) -> dict:
        if self.instance is None:  # criação
            self.executar_validacao(ConsuladoService().validar_criacao, self.usuario_logado)
        return attrs


class MembroConsuladoSerializer(serializers.ModelSerializer):
    usuario = UsuarioResumoSerializer(read_only=True)

    class Meta:
        model = MembroConsulado
        fields = ("id", "usuario", "cargo", "data_filiacao")
        read_only_fields = fields


class SolicitacaoMembroSerializer(serializers.ModelSerializer):
    usuario = UsuarioResumoSerializer(read_only=True)

    class Meta:
        model = SolicitacaoMembro
        fields = ("id", "usuario", "consulado", "status_aprovacao", "criado_em", "respondido_em")
        read_only_fields = fields
