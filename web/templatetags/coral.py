"""Filtros de formatação usados nos templates (datas em português, plurais, rótulos)."""
from __future__ import annotations

from datetime import datetime

from django import template
from django.utils import timezone

from core.models import CategoriaAliado, MandoCampo, TipoUsuario

register = template.Library()

DIAS_DA_SEMANA = ("Segunda-feira", "Terça-feira", "Quarta-feira", "Quinta-feira", "Sexta-feira", "Sábado", "Domingo")
MESES = (
    "janeiro", "fevereiro", "março", "abril", "maio", "junho",
    "julho", "agosto", "setembro", "outubro", "novembro", "dezembro",
)

PAPEIS = {
    TipoUsuario.ADMIN: "Administrador",
    TipoUsuario.RESPONSAVEL_CONSULADO: "Responsável por consulado",
    TipoUsuario.RESPONSAVEL_ALIADO: "Responsável por aliado",
}

ICONES_CATEGORIA = {
    CategoriaAliado.BAR: "sports_bar",
    CategoriaAliado.RESTAURANTE: "restaurant",
    CategoriaAliado.VESTUARIO: "checkroom",
    CategoriaAliado.LOJA: "storefront",
    CategoriaAliado.SERVICOS: "handyman",
}


@register.filter
def hora(valor: datetime) -> str:
    """Ex.: "17h" ou "17h30"."""
    d = timezone.localtime(valor)
    return f"{d.hour}h" if d.minute == 0 else f"{d.hour}h{d.minute:02d}"


@register.filter
def dia_hora(valor: datetime) -> str:
    """Ex.: "Sábado, 26/09/2026 às 17h"."""
    d = timezone.localtime(valor)
    return f"{DIAS_DA_SEMANA[d.weekday()]}, {d:%d/%m/%Y} às {hora(d)}"


@register.filter
def dia(valor: datetime) -> str:
    return f"{timezone.localtime(valor):%d}"


@register.filter
def mes_abreviado(valor: datetime) -> str:
    """Ex.: "SET"."""
    return MESES[timezone.localtime(valor).month - 1][:3].upper()


@register.filter
def mes_ano(valor: datetime) -> str:
    """Ex.: "Setembro 2026"."""
    d = timezone.localtime(valor)
    return f"{MESES[d.month - 1].capitalize()} {d.year}"


@register.filter
def membros(total: int) -> str:
    """"1 membro", "2 membros", "0 membros"."""
    return f"{total} {'membro' if total == 1 else 'membros'}"


@register.filter
def confronto(partida) -> str:
    """Mandante sempre à esquerda, como no placar."""
    if partida.mando_campo == MandoCampo.CASA:
        return f"Santa Cruz x {partida.adversario}"
    return f"{partida.adversario} x Santa Cruz"


@register.filter
def papel(usuario) -> str:
    return "Administrador" if usuario.is_admin else PAPEIS.get(usuario.tipo_usuario, "Torcedor")


@register.filter
def icone_categoria(categoria: str) -> str:
    return ICONES_CATEGORIA.get(categoria, "more_horiz")


@register.filter
def inicial(nome: str) -> str:
    return nome[:1].upper() if nome else "?"
