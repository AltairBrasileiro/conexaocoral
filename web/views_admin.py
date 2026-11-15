"""
Telas de administração (abas do "Painel do Administrador").

Substituem o Django Admin no dia a dia dos gestores: negócios da vitrine,
contas de usuários e calendário de partidas. As abas "Solicitações" (novos
consulados) e "Reportes" ficam em ``web.views``. Tudo aqui é exclusivo de
administradores e passa pelos mesmos serviços da API.
"""
from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.db.models.functions import Lower
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from core.exceptions import RegraNegocioError
from core.models import Aliado, Partida, StatusAprovacao, TipoUsuario, Usuario
from core.repositories import AliadoRepository
from core.services import AliadoService, PartidaService, UsuarioService
from web.forms import PAPEIS_ROTULOS, PapelForm, PartidaForm, RejeicaoForm
from web.views import _executar, _exigir_admin, _voltar, contadores_admin

# Linhas por página nas listas de contas e de negócios.
LIMITE_LISTA = 50


def _contexto(request: HttpRequest, subaba: str, **extra) -> dict:
    return {"aba": "painel", "subaba": subaba, **contadores_admin(request.user), **extra}


# ------------------------------------------------------- negócios (aliados)
@login_required
def negocios(request: HttpRequest) -> HttpResponse:
    """Aba "Negócios": cadastros aguardando análise e os demais, com busca."""
    _exigir_admin(request.user)
    busca = request.GET.get("q", "").strip()
    todos = AliadoRepository().get_queryset()
    pendentes = todos.filter(status_aprovacao=StatusAprovacao.PENDENTE).order_by("criado_em")
    avaliados = todos.exclude(status_aprovacao=StatusAprovacao.PENDENTE)
    if busca:
        avaliados = avaliados.filter(
            Q(nome_negocio__icontains=busca) | Q(usuario__nome__icontains=busca) | Q(usuario__email__icontains=busca)
        )
    return render(request, "web/admin_negocios.html", _contexto(
        request, "negocios",
        pendentes=list(pendentes),
        avaliados=list(avaliados.order_by("-status_aprovacao", Lower("nome_negocio"))[:LIMITE_LISTA]),
        busca=busca,
        form_rejeicao=RejeicaoForm(),
    ))


@login_required
@require_POST
def moderar_negocio(request: HttpRequest, pk: int) -> HttpResponse:
    """``acao``: aprovar, rejeitar (com ``motivo``), selo ou tirar-selo."""
    _exigir_admin(request.user)
    aliado = get_object_or_404(Aliado.objects.select_related("usuario"), pk=pk)
    servico, acao, admin = AliadoService(), request.POST.get("acao"), request.user
    if acao == "aprovar":
        sucesso = f"{aliado.nome_negocio} aprovado e publicado na vitrine."
        if aliado.usuario.is_torcedor:
            sucesso += f" {aliado.usuario.nome} agora é lojista."
        _executar(request, lambda: servico.aprovar(aliado, moderador=admin), sucesso)
    elif acao == "rejeitar":
        form = RejeicaoForm(request.POST)
        motivo = form.cleaned_data["motivo"] if form.is_valid() else ""
        _executar(
            request, lambda: servico.rejeitar(aliado, moderador=admin, motivo=motivo),
            f"{aliado.nome_negocio} recusado: não aparece na vitrine.",
        )
    elif acao == "selo":
        _executar(request, lambda: servico.definir_selo(aliado, verificado=True, moderador=admin),
                  f"{aliado.nome_negocio} recebeu o selo de verificado.")
    elif acao == "tirar-selo":
        _executar(request, lambda: servico.definir_selo(aliado, verificado=False, moderador=admin),
                  f"Selo de verificado retirado de {aliado.nome_negocio}.")
    else:
        messages.error(request, "Ação desconhecida.")
    return _voltar(request, "web:admin-negocios")


# ------------------------------------------------------------------ usuários
@login_required
def usuarios(request: HttpRequest) -> HttpResponse:
    """Aba "Usuários": busca contas, troca o papel e bloqueia ou libera o acesso."""
    _exigir_admin(request.user)
    busca = request.GET.get("q", "").strip()
    papel = request.GET.get("papel", "")
    lista = Usuario.objects.annotate(
        total_consulados=Count("consulados_responsavel", distinct=True),
        total_negocios=Count("aliados", distinct=True),
    )
    if busca:
        lista = lista.filter(Q(nome__icontains=busca) | Q(email__icontains=busca))
    if papel == "bloqueados":
        lista = lista.filter(is_active=False)
    elif papel in TipoUsuario.values:
        lista = lista.filter(tipo_usuario=papel)
    else:
        papel = ""
    total = lista.count()
    return render(request, "web/admin_usuarios.html", _contexto(
        request, "usuarios",
        usuarios=list(lista.order_by(Lower("nome"))[:LIMITE_LISTA]),
        total=total,
        limite=LIMITE_LISTA,
        busca=busca,
        papel=papel,
        papeis=PAPEIS_ROTULOS,
    ))


@login_required
@require_POST
def papel_usuario(request: HttpRequest, pk: int) -> HttpResponse:
    _exigir_admin(request.user)
    usuario = get_object_or_404(Usuario, pk=pk)
    form = PapelForm(request.POST)
    if form.is_valid():
        tipo = form.cleaned_data["tipo_usuario"]
        _executar(
            request, lambda: UsuarioService().definir_papel(request.user, usuario, tipo),
            f"{usuario.nome} agora é {dict(PAPEIS_ROTULOS)[tipo]}.",
        )
    else:
        messages.error(request, "Escolha um papel válido.")
    return _voltar(request, "web:admin-usuarios")


@login_required
@require_POST
def acesso_usuario(request: HttpRequest, pk: int) -> HttpResponse:
    """``acao=bloquear`` impede a conta de entrar; ``acao=liberar`` devolve o acesso."""
    _exigir_admin(request.user)
    usuario = get_object_or_404(Usuario, pk=pk)
    ativo = request.POST.get("acao") == "liberar"
    _executar(
        request, lambda: UsuarioService().definir_ativo(request.user, usuario, ativo),
        f"Acesso de {usuario.nome} liberado." if ativo else f"Acesso de {usuario.nome} bloqueado.",
    )
    return _voltar(request, "web:admin-usuarios")


# ------------------------------------------------------------------ partidas
@login_required
def partidas(request: HttpRequest) -> HttpResponse:
    """Aba "Partidas": calendário com cadastro, edição e exclusão."""
    _exigir_admin(request.user)
    anteriores = request.GET.get("periodo") == "anteriores"
    agora = timezone.now()
    if anteriores:
        lista = Partida.objects.filter(data_hora__lt=agora).order_by("-data_hora")[:LIMITE_LISTA]
    else:
        lista = Partida.objects.filter(data_hora__gte=agora).order_by("data_hora")
    return render(request, "web/admin_partidas.html", _contexto(
        request, "partidas", partidas=list(lista), anteriores=anteriores,
    ))


def _salvar_partida(request: HttpRequest, form: PartidaForm, partida: Partida | None) -> HttpResponse | None:
    """Grava pelo serviço; devolve o redirecionamento ou None (com o erro no formulário)."""
    servico = PartidaService()
    try:
        if partida is None:
            servico.criar_partida(request.user, **form.cleaned_data)
        else:
            servico.atualizar_partida(request.user, partida, **form.cleaned_data)
    except RegraNegocioError as erro:
        form.add_error(erro.campo if erro.campo in form.fields else None, erro.mensagem)
        return None
    messages.success(request, "Partida cadastrada no calendário." if partida is None else "Partida atualizada.")
    return redirect("web:admin-partidas")


@login_required
def nova_partida(request: HttpRequest) -> HttpResponse:
    _exigir_admin(request.user)
    form = PartidaForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        resposta = _salvar_partida(request, form, None)
        if resposta:
            return resposta
    return render(request, "web/admin_partida_form.html", _contexto(request, "partidas", form=form))


@login_required
def editar_partida(request: HttpRequest, pk: int) -> HttpResponse:
    _exigir_admin(request.user)
    partida = get_object_or_404(Partida, pk=pk)
    form = PartidaForm(request.POST or None, instance=partida)
    if request.method == "POST" and form.is_valid():
        resposta = _salvar_partida(request, form, partida)
        if resposta:
            return resposta
    return render(request, "web/admin_partida_form.html", _contexto(request, "partidas", form=form, partida=partida))


@login_required
@require_POST
def excluir_partida(request: HttpRequest, pk: int) -> HttpResponse:
    _exigir_admin(request.user)
    partida = get_object_or_404(Partida, pk=pk)
    _executar(request, lambda: PartidaService().excluir_partida(request.user, partida), "Partida excluída do calendário.")
    return redirect("web:admin-partidas")
