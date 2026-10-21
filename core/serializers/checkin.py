from __future__ import annotations

from rest_framework import serializers

from core.models import CheckIn, Consulado, Partida
from core.serializers.base import UsuarioResumoSerializer, ValidacaoServiceMixin
from core.serializers.partida import PartidaResumoSerializer
from core.services import CheckInService


class CheckInSerializer(ValidacaoServiceMixin, serializers.ModelSerializer):
    # Entrada: IDs. Saída: dados resumidos para o front-end.
    partida = serializers.PrimaryKeyRelatedField(queryset=Partida.objects.all())
    consulado = serializers.PrimaryKeyRelatedField(queryset=Consulado.objects.all())
    partida_detalhe = PartidaResumoSerializer(source="partida", read_only=True)
    consulado_nome = serializers.CharField(source="consulado.nome", read_only=True)
    usuario = UsuarioResumoSerializer(read_only=True)

    class Meta:
        model = CheckIn
        fields = (
            "id", "usuario", "partida", "partida_detalhe",
            "consulado", "consulado_nome", "data_checkin", "ativo",
        )
        read_only_fields = ("id", "data_checkin", "ativo")

    def validate(self, attrs: dict) -> dict:
        # Regras: consulado aprovado, janela da partida e 1 check-in ativo por partida.
        self.executar_validacao(
            CheckInService().validar_checkin, self.usuario_logado, attrs["partida"], attrs["consulado"],
        )
        return attrs
