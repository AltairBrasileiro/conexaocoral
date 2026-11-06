"""
Páginas da interface web.

As views só montam o contexto e delegam as regras aos mesmos serviços e
repositórios usados pela API REST, então membros, eventos e visibilidade
seguem exatamente as mesmas regras nos dois canais.
"""
from __future__ import annotations

from collections.abc import Callable
from datetime import timedelta
from decimal import Decimal
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
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.text import slugify
from django.views.decorators.http import require_POST

from core.exceptions import RegraNegocioError
from core.models import (
    CategoriaAliado, Consulado, Evento, MembroConsulado, Partida, PresencaEvento, Reporte, StatusAprovacao,
    Usuario,
)
from core.repositories import (
    AliadoRepository, ConsuladoRepository, EventoRepository, FotoConsuladoRepository,
    MembroConsuladoRepository, SolicitacaoMembroRepository,
)
from core.services import ConsuladoService, EventoService, ReporteService
from web.forms import (
    CARGOS, OUTRO_CARGO, CargoForm, ConsuladoForm, EntrarForm, EventoForm, FotoConsuladoForm, LegendaFotoForm,
    NovoMembroForm, RejeicaoForm, ReporteForm, SolicitacaoConsuladoForm,
)
from web.pdf import lista_de_presenca
from web.pix import codigo_pix, qr_svg

# Campo do serviço (EventoService) -> campo do formulário de evento, para mostrar o erro no lugar certo.
CAMPOS_DO_EVENTO = {
    "data_hora_inicio": "inicio", "data_hora_fim": "inicio", "limite_vagas": "limite_vagas", "fotos": "fotos",
}

# Membros da equipe exibidos na página pública antes do "Ver todos".
EQUIPE_VISIVEL = 5

# Um jogo em andamento (começou há menos de 3h) ainda aparece como "próximo jogo".
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


def tem_painel(usuario: Usuario) -> bool:
    """Admin, embaixador, ou membro com cargo (que no Painel edita as fotos do consulado)."""
    if usuario.is_admin or usuario.is_responsavel_consulado:
        return True
    return MembroConsuladoRepository().consulados_com_cargo(usuario).exists()


def _consulado_administrado(usuario: Usuario, pk: int) -> Consulado:
    consulado = get_object_or_404(Consulado, pk=pk)
    if not (usuario.is_admin or consulado.responsavel_id == usuario.id):
        raise PermissionDenied("Você só pode alterar consulados que administra.")
    return consulado


def _evento_administrado(usuario: Usuario, pk: int) -> Evento:
    evento = get_object_or_404(Evento.objects.select_related("consulado"), pk=pk)
    if not (usuario.is_admin or evento.consulado.responsavel_id == usuario.id):
        raise PermissionDenied("Você só pode alterar eventos dos consulados que administra.")
    return evento


def _exigir_admin(usuario: Usuario) -> None:
    if not usuario.is_admin:
        raise PermissionDenied("Apenas administradores avaliam as solicitações de consulados.")


def _total_solicitacoes(usuario: Usuario) -> int | None:
    """Quantidade de solicitações pendentes, exibida na aba do admin (None para os demais)."""
    if not usuario.is_admin:
        return None
    return Consulado.objects.filter(status_aprovacao=StatusAprovacao.PENDENTE).count()


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
    servico = ConsuladoService()
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
            "foto": fotos[0].src if fotos else "",
            "membros": c.total_membros,
            "eh_membro": bool(c.eh_membro),
            "whatsapp": c.link_whatsapp if servico.pode_ver_whatsapp(request.user, c) else "",
            "whatsapp_so_membros": bool(c.link_whatsapp) and not servico.pode_ver_whatsapp(request.user, c),
            "url": reverse("web:consulado", args=[c.id]),
        })
    return render(request, "web/consulados.html", {
        "aba": "consulados",
        "consulados": dados,
        # Os consulados de que o torcedor já é membro aparecem em destaque ao abrir o mapa.
        "meus_consulados": [c for c in dados if c["eh_membro"]],
    })


@login_required
def consulado_detalhe(request: HttpRequest, pk: int) -> HttpResponse:
    """Módulo 2 — Detalhes do consulado, equipe, próximo jogo e eventos."""
    consulado = get_object_or_404(ConsuladoRepository().visiveis_para(request.user), pk=pk)
    partida = _proxima_partida()
    eventos = (
        EventoRepository().visiveis_para(request.user).filter(consulado=consulado)
        .prefetch_related("fotos").order_by("data_hora_inicio")
    )
    # Eventos de que o organizador retirou a presença deste usuário.
    retiradas = set(
        PresencaEvento.todas.filter(usuario=request.user, evento__consulado=consulado, removida_em__isnull=False)
        .values_list("evento_id", flat=True)
    )
    # Equipe exibida na página pública: o embaixador primeiro, depois os membros com cargo.
    equipe = [{"nome": consulado.responsavel.nome, "cargo": "Embaixador"}] if consulado.responsavel_id else []
    # Ordem da hierarquia da lista de cargos (Vice-presidente primeiro); cargos personalizados no fim.
    def ordem(membro: MembroConsulado) -> tuple:
        posicao = CARGOS.index(membro.cargo) if membro.cargo in CARGOS else len(CARGOS)
        return posicao, membro.cargo.lower(), membro.usuario.nome.lower()

    com_cargo = (
        MembroConsuladoRepository().membros_do_consulado(consulado)
        .exclude(usuario_id=consulado.responsavel_id)
        .exclude(cargo="")
    )
    equipe += [{"nome": m.usuario.nome, "cargo": m.cargo} for m in sorted(com_cargo, key=ordem)]
    return render(request, "web/consulado_detalhe.html", {
        "aba": "consulados",
        "consulado": consulado,
        "equipe_visivel": equipe[:EQUIPE_VISIVEL],
        "equipe_oculta": equipe[EQUIPE_VISIVEL:],
        "total_equipe": len(equipe),
        "eh_responsavel": consulado.responsavel_id == request.user.id,
        "pedido_pendente": SolicitacaoMembroRepository().pendente(request.user, consulado),
        "presencas_retiradas": retiradas,
        "pode_ver_confirmados": EventoService().pode_gerir_presencas_do_consulado(request.user, consulado),
        "pode_gerenciar": request.user.is_admin or consulado.responsavel_id == request.user.id,
        "pode_ver_whatsapp": ConsuladoService().pode_ver_whatsapp(request.user, consulado),
        "fotos": list(consulado.fotos.all()),
        "partida": partida,
        "eventos": list(eventos),
        "agora": timezone.now(),
    })


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
    """
    Módulo 5 — Painel do consulado.

    O admin acompanha todos e o embaixador, os que administra (com todas as
    configurações). Membros com cargo veem os consulados em que têm cargo, só
    com a edição das fotos.
    """
    if not tem_painel(request.user):
        raise PermissionDenied("O painel é exclusivo para embaixadores e membros com cargo no consulado.")

    cargos = {f.consulado_id: f.cargo for f in MembroConsuladoRepository().consulados_com_cargo(request.user)}
    lista = ConsuladoRepository().visiveis_para(request.user).order_by("nome")
    if not request.user.is_admin:
        lista = lista.filter(Q(responsavel=request.user) | Q(pk__in=cargos.keys()))
    meus = list(lista)
    contexto: dict[str, Any] = {
        "aba": "painel", "subaba": "consulados", "consulados": meus,
        "total_solicitacoes": _total_solicitacoes(request.user),
        "total_reportes": _total_reportes(request.user),
    }
    if not meus:
        return render(request, "web/painel.html", contexto)

    escolhido = next((c for c in meus if str(c.id) == request.GET.get("consulado")), meus[0])
    pode_gerir = request.user.is_admin or escolhido.responsavel_id == request.user.id
    contexto.update(
        consulado=escolhido,
        pode_gerir=pode_gerir,
        meu_cargo=cargos.get(escolhido.id, ""),
        pode_editar_fotos=ConsuladoService().pode_editar_fotos(request.user, escolhido),
        fotos=list(FotoConsuladoRepository().do_consulado(escolhido)),
    )
    if not pode_gerir:
        # Membro com cargo: fotos e a lista de confirmados dos eventos do consulado.
        contexto["eventos"] = list(
            EventoRepository().visiveis_para(request.user).filter(consulado=escolhido).order_by("data_hora_inicio")
        )
        contexto["agora"] = timezone.now()
        return render(request, "web/painel.html", contexto)

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
        pedidos_entrada=SolicitacaoMembroRepository().pendentes_do_consulado(escolhido).count(),
        eventos=eventos,
        eventos_futuros=len(futuros),
        presencas_previstas=presencas_previstas,
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
    form = EventoForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        try:
            evento = EventoService().criar_evento(
                request.user, consulado=consulado, fotos=form.cleaned_data["fotos"], **form.dados_evento(),
            )
        except RegraNegocioError as erro:
            campo = CAMPOS_DO_EVENTO.get(erro.campo)
            form.add_error(campo, erro.mensagem)
        else:
            messages.success(
                request,
                "Evento publicado." if evento.aprovado
                else "Evento criado! Ele aparece para a torcida após a aprovação.",
            )
            return redirect(_url_painel(consulado))
    return render(request, "web/novo_evento.html", {
        "aba": "painel", "consulado": consulado, "form": form, "maximo_fotos_evento": EventoService.MAXIMO_FOTOS,
    })


@login_required
def editar_evento(request: HttpRequest, pk: int) -> HttpResponse:
    evento = _evento_administrado(request.user, pk)
    form = EventoForm.para_evento(evento, request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        try:
            EventoService().atualizar_evento(
                evento, request.user,
                fotos_novas=form.cleaned_data["fotos"],
                remover_fotos=form.cleaned_data["remover_fotos"],
                **form.dados_evento(),
            )
        except RegraNegocioError as erro:
            campo = CAMPOS_DO_EVENTO.get(erro.campo)
            form.add_error(campo, erro.mensagem)
        else:
            messages.success(request, f'Evento "{evento.titulo}" atualizado.')
            return redirect(_url_painel(evento.consulado))
    return render(request, "web/editar_evento.html", {
        "aba": "painel", "consulado": evento.consulado, "evento": evento, "form": form,
        "maximo_fotos_evento": EventoService.MAXIMO_FOTOS,
    })


@login_required
@require_POST
def excluir_evento(request: HttpRequest, pk: int) -> HttpResponse:
    evento = _evento_administrado(request.user, pk)
    titulo, consulado = evento.titulo, evento.consulado
    _executar(request, lambda: EventoService().excluir_evento(evento, request.user), f'Evento "{titulo}" excluído.')
    return redirect(_url_painel(consulado))


# ------------------------------------------------------------------ membros
@login_required
def membros(request: HttpRequest, pk: int) -> HttpResponse:
    """Gestão dos membros do consulado pelo embaixador: cadastro, cargos e remoção."""
    consulado = _consulado_administrado(request.user, pk)
    form = NovoMembroForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            membro, senha = ConsuladoService().cadastrar_membro(request.user, consulado, **form.dados_membro())
        except RegraNegocioError as erro:
            form.add_error(erro.campo if erro.campo in form.fields else None, erro.mensagem)
        else:
            messages.success(request, f"{membro.usuario.nome} agora é membro do {consulado.nome}.")
            if senha:
                # Exibida uma única vez na página (não some como os avisos), para ser repassada.
                request.session["nova_conta"] = {"nome": membro.usuario.nome, "email": membro.usuario.email, "senha": senha}
            return redirect("web:membros", pk=consulado.pk)

    repositorio = MembroConsuladoRepository()
    outros = repositorio.outros_consulados_dos_membros(consulado)
    lista = list(repositorio.membros_do_consulado(consulado).order_by(Lower("usuario__nome")))
    for membro in lista:
        membro.outros_consulados = outros.get(membro.usuario_id, [])
    return render(request, "web/membros.html", {
        "aba": "painel",
        "consulado": consulado,
        "membros": lista,
        "pedidos": list(SolicitacaoMembroRepository().pendentes_do_consulado(consulado)),
        "form": form,
        "cargos": CARGOS,
        "outro_cargo": OUTRO_CARGO,
        "nova_conta": request.session.pop("nova_conta", None),
    })


def _membro_administrado(usuario: Usuario, pk: int) -> MembroConsulado:
    membro = get_object_or_404(MembroConsulado.objects.select_related("usuario", "consulado"), pk=pk)
    _consulado_administrado(usuario, membro.consulado_id)
    return membro


@login_required
@require_POST
def definir_cargo(request: HttpRequest, pk: int) -> HttpResponse:
    membro = _membro_administrado(request.user, pk)
    form = CargoForm(request.POST)
    if form.is_valid():
        cargo = form.cleaned_data["cargo"].strip()
        sucesso = f"Cargo de {membro.usuario.nome}: {cargo}." if cargo else f"Cargo de {membro.usuario.nome} removido."
        _executar(request, lambda: ConsuladoService().definir_cargo(request.user, membro, cargo), sucesso)
    else:
        messages.error(request, " ".join(e for erros in form.errors.values() for e in erros))
    return redirect("web:membros", pk=membro.consulado_id)


@login_required
@require_POST
def remover_membro(request: HttpRequest, pk: int) -> HttpResponse:
    membro = _membro_administrado(request.user, pk)
    _executar(
        request,
        lambda: ConsuladoService().remover_membro(request.user, membro),
        f"{membro.usuario.nome} não é mais membro do {membro.consulado.nome}.",
    )
    return redirect("web:membros", pk=membro.consulado_id)


# -------------------------------------------------- solicitações de consulado
@login_required
def solicitar_consulado(request: HttpRequest) -> HttpResponse:
    """Torcedor pede o cadastro de um novo consulado, de acordo com os requisitos do clube."""
    servico = ConsuladoService()
    form = SolicitacaoConsuladoForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        dados = {campo: valor for campo, valor in form.cleaned_data.items() if campo != "aceite_requisitos"}
        try:
            consulado = servico.criar_consulado(request.user, **dados)
        except RegraNegocioError as erro:
            form.add_error(None, erro.mensagem)
        else:
            messages.success(
                request,
                f"{consulado.nome} cadastrado." if consulado.aprovado
                else "Solicitação enviada! A administração vai analisar o cadastro do seu consulado.",
            )
            return redirect("web:solicitar-consulado")

    minhas = Consulado.objects.filter(responsavel=request.user).order_by("-criado_em")
    return render(request, "web/solicitar_consulado.html", {
        "aba": "consulados",
        "form": form,
        "requisitos": settings.CONEXAO_CORAL.get("REQUISITOS_CONSULADO", []),
        "minhas_solicitacoes": list(minhas),
    })


@login_required
def solicitacoes(request: HttpRequest) -> HttpResponse:
    """Aba "Solicitações" do painel do administrador."""
    _exigir_admin(request.user)
    pendentes = (
        Consulado.objects.filter(status_aprovacao=StatusAprovacao.PENDENTE)
        .select_related("responsavel")
        .prefetch_related("fotos")
        .order_by("criado_em")
    )
    recentes = (
        Consulado.objects.exclude(status_aprovacao=StatusAprovacao.PENDENTE)
        .select_related("responsavel")
        .order_by("-criado_em")[:10]
    )
    return render(request, "web/solicitacoes.html", {
        "aba": "painel",
        "subaba": "solicitacoes",
        "pendentes": list(pendentes),
        "recentes": list(recentes),
        "total_solicitacoes": len(pendentes),
        "total_reportes": _total_reportes(request.user),
        "form_rejeicao": RejeicaoForm(),
    })


@login_required
@require_POST
def aprovar_solicitacao(request: HttpRequest, pk: int) -> HttpResponse:
    _exigir_admin(request.user)
    consulado = get_object_or_404(Consulado.objects.select_related("responsavel"), pk=pk)
    era_torcedor = consulado.responsavel.is_torcedor
    sucesso = f"{consulado.nome} aprovado e publicado no mapa."
    if era_torcedor:
        sucesso += f" {consulado.responsavel.nome} agora é embaixador."
    _executar(request, lambda: ConsuladoService().aprovar_solicitacao(consulado, moderador=request.user), sucesso)
    return redirect("web:solicitacoes")


@login_required
@require_POST
def rejeitar_solicitacao(request: HttpRequest, pk: int) -> HttpResponse:
    _exigir_admin(request.user)
    consulado = get_object_or_404(Consulado, pk=pk)
    form = RejeicaoForm(request.POST)
    motivo = form.cleaned_data["motivo"] if form.is_valid() else ""
    _executar(
        request,
        lambda: ConsuladoService().rejeitar_solicitacao(consulado, moderador=request.user, motivo=motivo),
        f"Solicitação de {consulado.nome} recusada.",
    )
    return redirect("web:solicitacoes")


# ---------------------------------------------------- membros: entrar e sair
def _voltar(request: HttpRequest, padrao: str) -> HttpResponse:
    """Volta para a página de origem (campo "proximo" do formulário), se for deste site."""
    destino = request.POST.get("proximo", "")
    if destino and url_has_allowed_host_and_scheme(destino, allowed_hosts={request.get_host()}):
        return redirect(destino)
    return redirect(padrao)


@login_required
@require_POST
def solicitar_entrada(request: HttpRequest, pk: int) -> HttpResponse:
    consulado = get_object_or_404(ConsuladoRepository().visiveis_para(request.user), pk=pk)
    _executar(
        request,
        lambda: ConsuladoService().solicitar_entrada(request.user, consulado),
        f"Pedido enviado! O embaixador do {consulado.nome} vai analisar a sua entrada.",
    )
    return _voltar(request, reverse("web:consulado", args=[consulado.pk]))


@login_required
@require_POST
def cancelar_pedido_entrada(request: HttpRequest, pk: int) -> HttpResponse:
    pedido = get_object_or_404(SolicitacaoMembroRepository().do_usuario(request.user), pk=pk)
    _executar(
        request,
        lambda: ConsuladoService().cancelar_solicitacao(request.user, pedido),
        f"Pedido para entrar no {pedido.consulado.nome} cancelado.",
    )
    return _voltar(request, reverse("web:minha-conta"))


@login_required
@require_POST
def sair_do_consulado(request: HttpRequest, pk: int) -> HttpResponse:
    consulado = get_object_or_404(Consulado, pk=pk)
    _executar(
        request,
        lambda: ConsuladoService().sair_do_consulado(request.user, consulado),
        f"Você saiu do {consulado.nome}.",
    )
    return _voltar(request, reverse("web:minha-conta"))


@login_required
@require_POST
def responder_pedido_entrada(request: HttpRequest, pk: int) -> HttpResponse:
    """O embaixador aprova (``decisao=aprovar``) ou recusa o pedido de entrada."""
    pedido = get_object_or_404(SolicitacaoMembroRepository().get_queryset(), pk=pk)
    _consulado_administrado(request.user, pedido.consulado_id)
    aprovar = request.POST.get("decisao") == "aprovar"
    nome = pedido.usuario.nome
    _executar(
        request,
        lambda: ConsuladoService().responder_solicitacao(request.user, pedido, aprovar=aprovar),
        f"{nome} agora é membro do consulado." if aprovar else f"Pedido de {nome} recusado.",
    )
    return redirect("web:membros", pk=pedido.consulado_id)


# --------------------------------------------------------------- minha conta
@login_required
def minha_conta(request: HttpRequest) -> HttpResponse:
    """Consulados de que o torcedor é membro (entrar/sair), pedidos e eventos com presença confirmada."""
    agora = timezone.now()
    filiacoes = list(
        MembroConsulado.objects.filter(usuario=request.user)
        .select_related("consulado")
        .order_by(Lower("consulado__nome"))
    )
    pedidos = list(
        SolicitacaoMembroRepository().do_usuario(request.user)
        .exclude(status_aprovacao=StatusAprovacao.APROVADO)
        .order_by("-criado_em")[:10]
    )
    presencas = list(
        PresencaEvento.objects.filter(usuario=request.user)
        .select_related("evento", "evento__consulado")
        .order_by("evento__data_hora_inicio")
    )
    return render(request, "web/minha_conta.html", {
        "aba": "conta",
        "filiacoes": filiacoes,
        "pedidos": pedidos,
        "eventos_proximos": [p for p in presencas if p.evento.data_hora_fim >= agora],
        "eventos_anteriores": [p for p in reversed(presencas) if p.evento.data_hora_fim < agora],
        "agora": agora,
    })


# ------------------------------------------------------------ fotos do consulado
def _consulado_com_fotos_editaveis(usuario: Usuario, pk: int) -> Consulado:
    """Só o embaixador ou um membro com cargo no consulado edita as fotos."""
    consulado = get_object_or_404(ConsuladoRepository().visiveis_para(usuario), pk=pk)
    if not ConsuladoService().pode_editar_fotos(usuario, consulado):
        raise PermissionDenied("Apenas o embaixador e os membros com cargo no consulado podem editar as fotos.")
    return consulado


def _foto_editavel(usuario: Usuario, pk: int):
    foto = get_object_or_404(FotoConsuladoRepository().get_queryset(), pk=pk)
    _consulado_com_fotos_editaveis(usuario, foto.consulado_id)
    return foto


@login_required
def fotos_consulado(request: HttpRequest, pk: int) -> HttpResponse:
    consulado = _consulado_com_fotos_editaveis(request.user, pk)
    servico = ConsuladoService()
    form = FotoConsuladoForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        try:
            servico.adicionar_foto(request.user, consulado, **form.cleaned_data)
        except RegraNegocioError as erro:
            form.add_error("imagem", erro.mensagem)
        else:
            messages.success(request, "Foto adicionada à galeria do consulado.")
            return redirect("web:fotos-consulado", pk=consulado.pk)
    fotos = list(FotoConsuladoRepository().do_consulado(consulado))
    return render(request, "web/fotos_consulado.html", {
        "aba": "painel",
        "consulado": consulado,
        "fotos": fotos,
        "form": form,
        "maximo_fotos": servico.MAXIMO_FOTOS,
        "pode_enviar": len(fotos) < servico.MAXIMO_FOTOS,
    })


@login_required
@require_POST
def legenda_foto(request: HttpRequest, pk: int) -> HttpResponse:
    foto = _foto_editavel(request.user, pk)
    form = LegendaFotoForm(request.POST)
    if form.is_valid():
        _executar(
            request,
            lambda: ConsuladoService().editar_legenda(request.user, foto, form.cleaned_data["legenda"]),
            "Legenda atualizada.",
        )
    else:
        messages.error(request, "A legenda pode ter no máximo 150 caracteres.")
    return redirect("web:fotos-consulado", pk=foto.consulado_id)


@login_required
@require_POST
def capa_foto(request: HttpRequest, pk: int) -> HttpResponse:
    foto = _foto_editavel(request.user, pk)
    _executar(request, lambda: ConsuladoService().definir_capa(request.user, foto), "Capa do consulado atualizada.")
    return redirect("web:fotos-consulado", pk=foto.consulado_id)


@login_required
@require_POST
def remover_foto(request: HttpRequest, pk: int) -> HttpResponse:
    foto = _foto_editavel(request.user, pk)
    consulado_id = foto.consulado_id
    _executar(request, lambda: ConsuladoService().remover_foto(request.user, foto), "Foto removida da galeria.")
    return redirect("web:fotos-consulado", pk=consulado_id)


# ------------------------------------------------------ presenças em eventos
@login_required
@require_POST
def desmarcar_presenca(request: HttpRequest, pk: int) -> HttpResponse:
    """O próprio torcedor desmarca a presença que tinha confirmado."""
    presenca = get_object_or_404(
        PresencaEvento.objects.select_related("evento"), evento_id=pk, usuario=request.user,
    )
    _executar(
        request,
        lambda: EventoService().cancelar_presenca(presenca, request.user),
        f'Presença em "{presenca.evento.titulo}" desmarcada.',
    )
    return _voltar(request, reverse("web:consulado", args=[presenca.evento.consulado_id]))


def _evento_com_lista(usuario: Usuario, pk: int) -> Evento:
    """Lista de confirmados: embaixador, membro com cargo no consulado ou admin."""
    evento = get_object_or_404(Evento.objects.select_related("consulado"), pk=pk)
    if not EventoService().pode_gerir_presencas(usuario, evento):
        raise PermissionDenied("Apenas o embaixador e os membros com cargo no consulado veem a lista de confirmados.")
    return evento


def _confirmados(evento: Evento) -> list[PresencaEvento]:
    return list(
        PresencaEvento.objects.filter(evento=evento).select_related("usuario").order_by(Lower("usuario__nome"))
    )


@login_required
def presencas_evento(request: HttpRequest, pk: int) -> HttpResponse:
    evento = _evento_com_lista(request.user, pk)
    presencas = _confirmados(evento)
    retiradas = list(
        PresencaEvento.todas.filter(evento=evento, removida_em__isnull=False)
        .select_related("usuario", "removida_por")
        .order_by("-removida_em")
    )
    return render(request, "web/presencas_evento.html", {
        "aba": "painel",
        "evento": evento,
        "consulado": evento.consulado,
        "presencas": presencas,
        "retiradas": retiradas,
        "vagas_restantes": (evento.limite_vagas - len(presencas)) if evento.limite_vagas else None,
    })


@login_required
@require_POST
def remover_presenca_evento(request: HttpRequest, pk: int) -> HttpResponse:
    presenca = get_object_or_404(PresencaEvento.objects.select_related("usuario", "evento__consulado"), pk=pk)
    _evento_com_lista(request.user, presenca.evento_id)
    nome, evento_id = presenca.usuario.nome, presenca.evento_id
    _executar(
        request,
        lambda: EventoService().remover_presenca(request.user, presenca),
        f"{nome} foi retirado(a) da lista de confirmados.",
    )
    return redirect("web:presencas-evento", pk=evento_id)


@login_required
@require_POST
def readmitir_presenca_evento(request: HttpRequest, pk: int) -> HttpResponse:
    presenca = get_object_or_404(PresencaEvento.todas.select_related("usuario"), pk=pk, removida_em__isnull=False)
    _evento_com_lista(request.user, presenca.evento_id)
    _executar(
        request,
        lambda: EventoService().readmitir_presenca(request.user, presenca),
        f"{presenca.usuario.nome} voltou para a lista de confirmados.",
    )
    return redirect("web:presencas-evento", pk=presenca.evento_id)


@login_required
def presencas_evento_pdf(request: HttpRequest, pk: int) -> HttpResponse:
    evento = _evento_com_lista(request.user, pk)
    resposta = HttpResponse(lista_de_presenca(evento, _confirmados(evento)), content_type="application/pdf")
    nome = slugify(f"lista-de-presenca-{evento.titulo}-{timezone.localtime(evento.data_hora_inicio):%d-%m-%Y}")
    resposta["Content-Disposition"] = f'attachment; filename="{nome}.pdf"'
    return resposta


# ------------------------------------------------------- problemas e sugestões
def _caminho_de_origem(request: HttpRequest) -> str:
    """Página de onde o usuário veio (só caminhos deste site), para anexar ao reporte."""
    origem = request.GET.get("de") or request.POST.get("pagina", "")
    if origem and url_has_allowed_host_and_scheme(origem, allowed_hosts={request.get_host()}):
        return origem[:300]
    return ""


@login_required
def reportar(request: HttpRequest) -> HttpResponse:
    form = ReporteForm(request.POST or None, request.FILES or None, initial={"pagina": _caminho_de_origem(request)})
    if request.method == "POST" and form.is_valid():
        dados = form.cleaned_data
        try:
            ReporteService().enviar(
                request.user, tipo=dados["tipo"], mensagem=dados["mensagem"],
                pagina=_caminho_de_origem(request), captura=dados["captura"],
            )
        except RegraNegocioError as erro:
            form.add_error(erro.campo if erro.campo in form.fields else None, erro.mensagem)
        else:
            messages.success(request, "Obrigado! Sua mensagem foi enviada para a equipe do Conexão Coral.")
            return redirect("web:reportar")
    return render(request, "web/reportar.html", {"aba": "conta", "form": form})


@login_required
def reportes(request: HttpRequest) -> HttpResponse:
    """Aba "Reportes" do painel do administrador."""
    _exigir_admin_reportes(request.user)
    status_filtro = request.GET.get("status", Reporte.Status.ABERTO)
    tipo_filtro = request.GET.get("tipo", "")
    lista = ReporteService().listar(request.user)
    if status_filtro in Reporte.Status.values:
        lista = lista.filter(status=status_filtro)
    else:
        status_filtro = ""
    if tipo_filtro in Reporte.Tipo.values:
        lista = lista.filter(tipo=tipo_filtro)
    else:
        tipo_filtro = ""
    return render(request, "web/reportes.html", {
        "aba": "painel",
        "subaba": "reportes",
        "reportes": list(lista[:100]),
        "status_filtro": status_filtro,
        "tipo_filtro": tipo_filtro,
        "status_opcoes": Reporte.Status.choices,
        "tipo_opcoes": Reporte.Tipo.choices,
        "total_solicitacoes": _total_solicitacoes(request.user),
        "total_reportes": _total_reportes(request.user),
    })


def _exigir_admin_reportes(usuario: Usuario) -> None:
    if not usuario.is_admin:
        raise PermissionDenied("Apenas administradores veem os reportes.")


def _total_reportes(usuario: Usuario) -> int | None:
    """Reportes em aberto, exibidos na aba do admin (None para os demais)."""
    return Reporte.objects.filter(status=Reporte.Status.ABERTO).count() if usuario.is_admin else None


@login_required
@require_POST
def responder_reporte(request: HttpRequest, pk: int) -> HttpResponse:
    _exigir_admin_reportes(request.user)
    reporte = get_object_or_404(Reporte, pk=pk)
    servico = ReporteService()
    if request.POST.get("acao") == "reabrir":
        _executar(request, lambda: servico.reabrir(request.user, reporte), f"Reporte #{reporte.pk} reaberto.")
    else:
        _executar(request, lambda: servico.marcar_resolvido(request.user, reporte), f"Reporte #{reporte.pk} resolvido.")
    return _voltar(request, reverse("web:reportes"))


# ---------------------------------------------------------- apoie o app (Pix)
VALORES_SUGERIDOS = (10, 25, 50, 100)


@login_required
def apoie(request: HttpRequest) -> HttpResponse:
    """Contribuição financeira com o desenvolvimento do app, via Pix (chave em settings)."""
    pix = settings.CONEXAO_CORAL["PIX"]
    valor_texto = request.GET.get("valor", "")
    valor = Decimal(valor_texto) if valor_texto.isdigit() and 0 < int(valor_texto) <= 10_000 else None
    codigo = codigo_pix(chave=pix["chave"], nome=pix["nome"], cidade=pix["cidade"], valor=valor)
    return render(request, "web/apoie.html", {
        "aba": "conta",
        "pix": pix,
        "valor": valor,
        "valores": VALORES_SUGERIDOS,
        "codigo_pix": codigo,
        "qr_svg": qr_svg(codigo),
    })
