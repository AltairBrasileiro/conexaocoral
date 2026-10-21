"""Funções auxiliares para criar dados de teste (sem dependências externas)."""
from __future__ import annotations

from datetime import timedelta
from itertools import count
from typing import Any

from django.utils import timezone

from core.models import Consulado, Evento, MandoCampo, Partida, StatusAprovacao, TipoUsuario, Usuario

_seq = count(1)


def criar_usuario(tipo: str = TipoUsuario.TORCEDOR, **extra: Any) -> Usuario:
    n = next(_seq)
    return Usuario.objects.create_user(
        email=extra.pop("email", f"usuario{n}@coral.com"),
        password=extra.pop("password", "SenhaForte#123"),
        nome=extra.pop("nome", f"Usuário {n}"),
        tipo_usuario=tipo,
        **extra,
    )


def criar_consulado(responsavel: Usuario | None = None, **extra: Any) -> Consulado:
    n = next(_seq)
    responsavel = responsavel or criar_usuario(TipoUsuario.RESPONSAVEL_CONSULADO)
    dados = {
        "nome": f"Consulado {n}",
        "endereco": "Rua Tal, 100",
        "latitude": "-7.115000",
        "longitude": "-34.863000",
        "status_aprovacao": StatusAprovacao.APROVADO,
    }
    dados.update(extra)
    return Consulado.objects.create(responsavel=responsavel, **dados)


def criar_partida(**extra: Any) -> Partida:
    dados = {
        "adversario": "Rival FC",
        "mando_campo": MandoCampo.CASA,
        "campeonato": "Campeonato Paraibano",
        "data_hora": timezone.now() + timedelta(hours=1),  # dentro da janela padrão de check-in
    }
    dados.update(extra)
    return Partida.objects.create(**dados)


def criar_evento(consulado: Consulado, **extra: Any) -> Evento:
    inicio = timezone.now() + timedelta(days=2)
    dados = {
        "titulo": "Resenha pós-jogo",
        "data_hora_inicio": inicio,
        "data_hora_fim": inicio + timedelta(hours=3),
        "status_aprovacao": StatusAprovacao.APROVADO,
    }
    dados.update(extra)
    return Evento.objects.create(consulado=consulado, **dados)
