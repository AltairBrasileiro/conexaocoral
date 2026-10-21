"""
Páginas da interface web.

As views só montam o contexto e delegam as regras aos mesmos serviços e
repositórios usados pela API REST, então check-in, eventos e visibilidade
seguem exatamente as mesmas regras nos dois canais.
"""
from __future__ import annotations

from collections.abc import Callable
from datetime import timedelta
from typing import Any

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Prefetch, Q
from django.db.models.functions import Lower
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from core.exceptions import RegraNegocioError
from core.models import CategoriaAliado, CheckIn, Consulado, Partida, PresencaEvento, Usuario
from core.repositories import AliadoRepository, CheckInRepository, ConsuladoRepository, EventoRepository
from core.services import CheckInService, EventoService
from web.forms import ConsuladoForm, EntrarForm, EventoForm

# Um jogo em andamento (começou há menos de 3h) ainda conta como "próximo".
DURACAO_JOGO = timedelta(hours=3)

# Contas criadas por "python manage.py popular_demo" (exibidas só com DEBUG).
CONTAS_DEMO = (
    ("Torcedor", "torcedor@coral.com"),
    ("Embaixador", "embaixador@coral.com"),
    ("Embaixador CoralJampa", "rubens.sousa@coral.com"),
    ("Lojista", "lojista@coral.com"),
    ("Admin", "admin@coral.com"),
)
SENHA_DEMO = "Coral@2026"

# Categorias da vitrine (valor, rótulo, ícone).
CATEGORIAS = (
    ("", "Todos", "apps"),
    (CategoriaAliado.BAR, "Bares", "sports_bar"),
    (CategoriaAliado.RESTAURANTE, "Restaurantes", "restaurant"),
    (CategoriaAliado.VESTUARIO, "Vestuário", "checkroom"),
    (CategoriaAliado.LOJA, "Lojas", "storefront"),
    (CategoriaAliado.SERVICOS, "Serviços", "handyman"),
    (CategoriaAliado.OUTROS, "Outros", "more_horiz"),
)


# --------------------------------------------------------------------- helpers
def _inicio_do_proximo_jogo():
    return timezone.now() - DURACAO_JOGO


def _proxima_partida() -> Partida | None:
    return Partida.objects.filter(data_hora__gte=_inicio_do_proximo_jogo()).order_by("data_hora").first()


def _executar(request: HttpRequest, acao: Callable[[], Any], sucesso: str) -> None:
    """Roda um comando de serviço e mostra o resultado como mensagem."""
    try:
        acao()
    except RegraNegocioError as erro:
        messages.error(request, erro.mensagem)
    else:
        messages.success(request, sucesso)


def _tem_painel(usuario: Usuario) -> bool:
    return usuario.is_admin or usuario.is_responsavel_consulado


def _consulado_administrado(usuario: Usuario, pk: int) -> Consulado:
    consulado = get_object_or_404(Consulado, pk=pk)
    if not (usuario.is_admin or consulado.responsavel_id == usuario.id):
        raise PermissionDenied("Você só pode alterar consulados que administra.")
    return consulado


def _url_painel(consulado: Consulado) -> str:
    return f"{reverse('web:painel')}?consulado={consulado.pk}"


# ------------------------------------------------------------------------ auth
class EntrarView(auth_views.LoginView):
    template_name = "web/login.html"
    authentication_form = EntrarForm
    redirect_authenticated_user = True

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        contexto = super().get_context_data(**kwargs)
        if settings.DEBUG:
            contexto.update(contas_demo=CONTAS_DEMO, senha_demo=SENHA_DEMO)
        return contexto


class SairView(auth_views.LogoutView):
    pass


# ----------------------------------------------------------------- consulados
@login_required
def consulados(request: HttpRequest) -> HttpResponse:
    """Módulo 1 — Mapa interativo com os consulados."""
    lista = ConsuladoRepository().visiveis_para(request.user).order_by("nome")
    dados = []
    for c in lista:
        fotos = list(c.fotos.all())
        dados.append({
            "id": c.id,
            "nome": c.nome,
            "endereco": c.endereco,
            "descricao": c.descricao,
            "lat": float(c.latitude),
            "lng": float(c.longitude),
            "logo": c.logo_url,
            "foto": fotos[0].url if fotos else "",
            "membros": c.total_membros,
            "eh_membro": bool(c.eh_membro),
            "whatsapp": c.link_whatsapp,
            "url": reverse("web:consulado", args=[c.id]),
        })
    return render(request, "web/consulados.html", {"aba": "consulados", "consulados": dados})


@login_required
def consulado_detalhe(request: HttpRequest, pk: int) -> HttpResponse:
    """Módulo 2 — Detalhes do consulado, check-in e eventos."""
    consulado = get_object_or_404(ConsuladoRepository().visiveis_para(request.user), pk=pk)
    partida = _proxima_partida()
    total_checkins, meu_checkin = 0, None
    if partida:
        total_checkins = CheckIn.objects.filter(partida=partida, consulado=consulado, ativo=True).count()
        meu_checkin = (
            CheckIn.objects.filter(partida=partida, usuario=request.user, ativo=True).select_related("consulado").first()
        )
    eventos = EventoRepository().visiveis_para(request.user).filter(consulado=consulado).order_by("data_hora_inicio")
    return render(request, "web/consulado_detalhe.html", {
        "aba": "consulados",
        "consulado": consulado,
        "fotos": list(consulado.fotos.all()),
        "partida": partida,
        "total_checkins": total_checkins,
        "meu_checkin": meu_checkin,
        "eventos": list(eventos),
        "agora": timezone.now(),
    })


@login_required
@require_POST
def fazer_checkin(request: HttpRequest, pk: int) -> HttpResponse:
    consulado = get_object_or_404(ConsuladoRepository().visiveis_para(request.user), pk=pk)
    partida_id = request.POST.get("partida", "")
    if not partida_id.isdigit():
        raise Http404("Partida inválida.")
    partida = get_object_or_404(Partida, pk=partida_id)
    sucesso = (
        "Check-in confirmado! Bom jogo, tricolor."
        if consulado.eh_membro
        else f"Check-in confirmado! Agora você é membro do {consulado.nome}."
    )
    _executar(request, lambda: CheckInService().realizar_checkin(request.user, partida, consulado), sucesso)
    return redirect("web:consulado", pk=consulado.pk)


@login_required
@require_POST
def cancelar_checkin(request: HttpRequest, pk: int) -> HttpResponse:
    checkin = get_object_or_404(CheckInRepository().visiveis_para(request.user), pk=pk)
    _executar(request, lambda: CheckInService().cancelar_checkin(checkin, request.user), "Check-in cancelado.")
    return redirect("web:consulado", pk=checkin.consulado_id)


@login_required
@require_POST
def confirmar_presenca(request: HttpRequest, pk: int) -> HttpResponse:
    evento = get_object_or_404(EventoRepository().visiveis_para(request.user), pk=pk)
    _executar(
        request,
        lambda: EventoService().confirmar_presenca(request.user, evento),
        f'Presença confirmada em "{evento.titulo}".',
    )
    return redirect("web:consulado", pk=evento.consulado_id)


# -------------------------------------------------------------------- partidas
@login_required
def partidas(request: HttpRequest) -> HttpResponse:
    """Módulo 3 — Calendário de partidas oficiais, agrupado por mês."""
    anteriores = request.GET.get("periodo") == "anteriores"
    corte = _inicio_do_proximo_jogo()
    if anteriores:
        lista = Partida.objects.filter(data_hora__lt=corte).order_by("-data_hora")
    else:
        lista = Partida.objects.filter(data_hora__gte=corte).order_by("data_hora")
    return render(request, "web/partidas.html", {
        "aba": "partidas",
        "anteriores": anteriores,
        "partidas": list(lista),
    })


# --------------------------------------------------------------------- aliados
@login_required
def aliados(request: HttpRequest) -> HttpResponse:
    """Módulo 4 — Vitrine de aliados (negócios de torcedores)."""
    categoria = request.GET.get("categoria", "")
    busca = request.GET.get("q", "").strip()
    lista = AliadoRepository().visiveis_para(request.user)
    if categoria in CategoriaAliado.values:
        lista = lista.filter(categoria=categoria)
    else:
        categoria = ""
    if busca:
        lista = lista.filter(Q(nome_negocio__icontains=busca) | Q(descricao__icontains=busca))
    # Verificados primeiro, depois em ordem alfabética.
    lista = lista.order_by("-selo_verificado", Lower("nome_negocio"))
    return render(request, "web/aliados.html", {
        "aba": "aliados",
        "aliados": list(lista),
        "categorias": CATEGORIAS,
        "categoria": categoria,
        "busca": busca,
    })


# ---------------------------------------------------------------------- painel
@login_required
def painel(request: HttpRequest) -> HttpResponse:
    """Módulo 5 — Painel restrito do embaixador (responsável pelo consulado)."""
    if not _tem_painel(request.user):
        raise PermissionDenied("O painel é exclusivo para responsáveis por consulado.")

    # O admin acompanha todos; o embaixador, só os que administra.
    lista = ConsuladoRepository().visiveis_para(request.user).order_by("nome")
    if not request.user.is_admin:
        lista = lista.filter(responsavel=request.user)
    meus = list(lista)
    contexto: dict[str, Any] = {"aba": "painel", "consulados": meus}
    if not meus:
        return render(request, "web/painel.html", contexto)

    escolhido = next((c for c in meus if str(c.id) == request.GET.get("consulado")), meus[0])
    partida = _proxima_partida()
    checkins = (
        list(
            CheckIn.objects.filter(partida=partida, consulado=escolhido, ativo=True)
            .select_related("usuario")
            .order_by("data_checkin")
        )
        if partida
        else []
    )
    eventos = list(
        EventoRepository()
        .visiveis_para(request.user)
        .filter(consulado=escolhido)
        .prefetch_related(Prefetch("presencas", queryset=PresencaEvento.objects.select_related("usuario")))
        .order_by("data_hora_inicio")
    )
    agora = timezone.now()
    futuros = [e for e in eventos if e.data_hora_fim >= agora]
    presencas_previstas = sum(e.total_confirmados for e in futuros)

    contexto.update(
        consulado=escolhido,
        partida=partida,
        checkins=checkins,
        eventos=eventos,
        eventos_futuros=len(futuros),
        presencas_previstas=presencas_previstas,
        publico_previsto=len(checkins) + presencas_previstas,
        agora=agora,
    )
    return render(request, "web/painel.html", contexto)


@login_required
def editar_consulado(request: HttpRequest, pk: int) -> HttpResponse:
    consulado = _consulado_administrado(request.user, pk)
    form = ConsuladoForm(request.POST or None, instance=consulado)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Dados do consulado atualizados.")
        return redirect(_url_painel(consulado))
    return render(request, "web/editar_consulado.html", {"aba": "painel", "consulado": consulado, "form": form})


@login_required
def novo_evento(request: HttpRequest, pk: int) -> HttpResponse:
    consulado = _consulado_administrado(request.user, pk)
    form = EventoForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            evento = EventoService().criar_evento(request.user, consulado=consulado, **form.dados_evento())
        except RegraNegocioError as erro:
            campo = "inicio" if erro.campo in ("data_hora_inicio", "data_hora_fim") else None
            form.add_error(campo, erro.mensagem)
        else:
            messages.success(
                request,
                "Evento publicado." if evento.aprovado
                else "Evento criado! Ele aparece para a torcida após a aprovação.",
            )
            return redirect(_url_painel(consulado))
    return render(request, "web/novo_evento.html", {"aba": "painel", "consulado": consulado, "form": form})
