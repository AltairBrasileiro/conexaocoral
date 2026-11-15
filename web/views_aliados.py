"""
Fluxo do lojista: "Meus negócios" na Vitrine da Torcida.

Qualquer usuário cadastra o próprio negócio; a administração aprova antes de
ele aparecer na vitrine. O dono edita e exclui o que cadastrou. As regras
ficam no ``AliadoService`` (o mesmo usado pela API).
"""
from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.files.uploadedfile import UploadedFile
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from core.exceptions import RegraNegocioError
from core.models import Aliado, Usuario
from core.repositories import AliadoRepository
from core.services import AliadoService
from web.forms import AliadoForm
from web.views import _executar


def _negocio_do_usuario(usuario: Usuario, pk: int) -> Aliado:
    """O dono (ou o admin) é quem edita e exclui o negócio."""
    aliado = get_object_or_404(AliadoRepository().get_queryset(), pk=pk)
    if not (usuario.is_admin or aliado.usuario_id == usuario.id):
        raise PermissionDenied("Você só pode alterar os negócios que cadastrou.")
    return aliado


def _voltar_para(request: HttpRequest, aliado: Aliado | None = None) -> str:
    """O admin que mexe no negócio de outra pessoa volta para a aba da administração."""
    if aliado is not None and request.user.is_admin and aliado.usuario_id != request.user.id:
        return "web:admin-negocios"
    return "web:meus-negocios"


def _erro_no_form(form: AliadoForm, erro: RegraNegocioError) -> None:
    form.add_error(erro.campo if erro.campo in form.fields else None, erro.mensagem)


@login_required
def meus_negocios(request: HttpRequest) -> HttpResponse:
    negocios = list(AliadoRepository().listar(usuario=request.user).order_by("-criado_em"))
    return render(request, "web/meus_negocios.html", {
        "aba": "aliados",
        "negocios": negocios,
        "pode_cadastrar": request.user.is_admin or len(negocios) < AliadoService.MAXIMO_POR_USUARIO,
        "maximo": AliadoService.MAXIMO_POR_USUARIO,
    })


@login_required
def novo_negocio(request: HttpRequest) -> HttpResponse:
    form = AliadoForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        foto = form.cleaned_data["foto"]
        try:
            aliado = AliadoService().criar_aliado(
                request.user, foto=foto if isinstance(foto, UploadedFile) else None, **form.dados_aliado(),
            )
        except RegraNegocioError as erro:
            _erro_no_form(form, erro)
        else:
            messages.success(
                request,
                f"{aliado.nome_negocio} publicado na Vitrine da Torcida." if aliado.aprovado
                else "Cadastro enviado! O negócio aparece na Vitrine da Torcida depois que a administração aprovar.",
            )
            return redirect("web:meus-negocios")
    return render(request, "web/negocio_form.html", {
        "aba": "aliados", "form": form, "voltar": "web:meus-negocios",
    })


@login_required
def editar_negocio(request: HttpRequest, pk: int) -> HttpResponse:
    aliado = _negocio_do_usuario(request.user, pk)
    voltar = _voltar_para(request, aliado)
    form = AliadoForm(request.POST or None, request.FILES or None, instance=aliado)
    if request.method == "POST" and form.is_valid():
        foto = form.cleaned_data["foto"]
        dados = {campo: form.cleaned_data[campo] for campo in form.changed_data if campo in form.Meta.fields}
        if isinstance(foto, UploadedFile):
            dados["foto"] = foto
        try:
            aliado = AliadoService().atualizar_aliado(aliado, request.user, remover_foto=foto is False, **dados)
        except RegraNegocioError as erro:
            _erro_no_form(form, erro)
        else:
            messages.success(
                request,
                "Dados do negócio atualizados." if aliado.aprovado
                else "Dados atualizados. O negócio volta para a vitrine depois que a administração aprovar de novo.",
            )
            return redirect(voltar)
    return render(request, "web/negocio_form.html", {
        "aba": "aliados", "form": form, "negocio": aliado, "voltar": voltar,
        # Quem não é admin e edita um cadastro aprovado precisa saber que ele volta para análise.
        "volta_para_analise": aliado.aprovado and not request.user.is_admin,
    })


@login_required
@require_POST
def excluir_negocio(request: HttpRequest, pk: int) -> HttpResponse:
    aliado = _negocio_do_usuario(request.user, pk)
    voltar, nome = _voltar_para(request, aliado), aliado.nome_negocio
    _executar(request, lambda: AliadoService().excluir_aliado(aliado, request.user), f"{nome} foi excluído.")
    return redirect(voltar)
