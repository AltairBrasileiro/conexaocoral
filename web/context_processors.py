"""Variáveis disponíveis em todos os templates da interface web."""
from __future__ import annotations

from django.http import HttpRequest


def navegacao(request: HttpRequest) -> dict:
    """``tem_painel``: mostra a aba "Painel" (admin, embaixador ou membro com cargo)."""
    usuario = getattr(request, "user", None)
    if not (usuario and usuario.is_authenticated):
        return {}
    from web.views import tem_painel  # import tardio: evita ciclo views ↔ settings na carga

    return {"tem_painel": tem_painel(usuario)}
