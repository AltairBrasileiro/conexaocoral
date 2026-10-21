from __future__ import annotations

from rest_framework import serializers

from core.models import Consulado, Evento, PresencaEvento
from core.serializers.base import UsuarioResumoSerializer, ValidacaoServiceMixin
from core.services import EventoService


class EventoSerializer(ValidacaoServiceMixin, serializers.ModelSerializer):
    consulado = serializers.PrimaryKeyRelatedField(queryset=Consulado.objects.all())
    consulado_nome = serializers.CharField(source="consulado.nome", read_only=True)
    total_confirmados = serializers.SerializerMethodField()
    confirmado = serializers.SerializerMethodField()

    class Meta:
        model = Evento
        fields = (
            "id", "consulado", "consulado_nome", "titulo", "descricao",
            "data_hora_inicio", "data_hora_fim", "exclusivo_membros",
            "status_aprovacao", "total_confirmados", "confirmado", "criado_em",
        )
        read_only_fields = ("id", "status_aprovacao", "criado_em")

    def get_total_confirmados(self, obj: Evento) -> int:
        valor = getattr(obj, "total_confirmados", None)
        return valor if valor is not None else obj.presencas.count()

    def get_confirmado(self, obj: Evento) -> bool:
        valor = getattr(obj, "confirmado", None)
        if valor is not None:
            return bool(valor)
        return obj.presencas.filter(usuario=self.usuario_logado).exists()

    def validate_consulado(self, valor: Consulado) -> Consulado:
        if self.instance is not None and valor.pk != self.instance.consulado_id:
            raise serializers.ValidationError("Não é permitido trocar o consulado organizador.")
        return valor

    def validate(self, attrs: dict) -> dict:
        # Em updates parciais, completa com os valores atuais para validar o conjunto.
        consulado = attrs.get("consulado", getattr(self.instance, "consulado", None))
        inicio = attrs.get("data_hora_inicio", getattr(self.instance, "data_hora_inicio", None))
        fim = attrs.get("data_hora_fim", getattr(self.instance, "data_hora_fim", None))
        self.executar_validacao(
            EventoService.validar_dados_evento,
            self.usuario_logado, consulado, inicio, fim, instancia=self.instance,
        )
        return attrs


class PresencaEventoSerializer(ValidacaoServiceMixin, serializers.ModelSerializer):
    evento = serializers.PrimaryKeyRelatedField(queryset=Evento.objects.select_related("consulado"))
    evento_titulo = serializers.CharField(source="evento.titulo", read_only=True)
    evento_inicio = serializers.DateTimeField(source="evento.data_hora_inicio", read_only=True)
    usuario = UsuarioResumoSerializer(read_only=True)

    class Meta:
        model = PresencaEvento
        fields = ("id", "usuario", "evento", "evento_titulo", "evento_inicio", "data_confirmacao")
        read_only_fields = ("id", "data_confirmacao")

    def validate(self, attrs: dict) -> dict:
        # Regra: apenas membros do consulado organizador podem confirmar presença.
        self.executar_validacao(EventoService().validar_confirmacao, self.usuario_logado, attrs["evento"])
        return attrs
