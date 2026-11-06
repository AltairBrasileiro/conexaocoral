"""
Regras de negócio de consulados e de seus membros.

* Qualquer usuário (torcedor ou responsável) pode solicitar o cadastro de um
  consulado; a solicitação nasce PENDENTE e o administrador aceita ou recusa.
  Cadastros feitos pelo administrador já nascem aprovados.
* Ao aceitar a solicitação de um torcedor, ele passa a ser Responsável por
  Consulado (embaixador).
* O embaixador gerencia os membros do próprio consulado: cadastra, remove e
  define cargos, que aparecem na página pública.
* Para entrar num consulado, o torcedor envia uma solicitação, que o
  embaixador aprova ou recusa.
  O membro pode sair quando quiser.
* O grupo do WhatsApp é obrigatório no cadastro do consulado, e o link só é
  mostrado aos membros (e ao embaixador e ao admin).
* As fotos do consulado só podem ser editadas pelo embaixador ou por um membro
  com cargo atribuído pelo embaixador.
"""
from __future__ import annotations

import secrets
from typing import Any

from django.core.files import File
from django.db import transaction

from core.exceptions import ConflitoError, PermissaoNegadaError, RecursoNaoEncontradoError, RegraNegocioError
from django.utils import timezone

from core.models import (
    Consulado, FotoConsulado, MembroConsulado, SolicitacaoMembro, StatusAprovacao, TipoUsuario, Usuario,
)
from core.repositories import (
    ConsuladoRepository, FotoConsuladoRepository, MembroConsuladoRepository, SolicitacaoMembroRepository,
    UsuarioRepository,
)
from core.services.aprovacao_service import AprovacaoService


class ConsuladoService:
    def __init__(
        self,
        repositorio: ConsuladoRepository | None = None,
        membro_repositorio: MembroConsuladoRepository | None = None,
        usuario_repositorio: UsuarioRepository | None = None,
        solicitacao_repositorio: SolicitacaoMembroRepository | None = None,
    ) -> None:
        self.repositorio = repositorio or ConsuladoRepository()
        self.membro_repositorio = membro_repositorio or MembroConsuladoRepository()
        self.usuario_repositorio = usuario_repositorio or UsuarioRepository()
        self.solicitacao_repositorio = solicitacao_repositorio or SolicitacaoMembroRepository()
        self.foto_repositorio = FotoConsuladoRepository()

    # ------------------------------------------------------------- cadastro
    PAPEIS_SOLICITANTES = frozenset({TipoUsuario.TORCEDOR, TipoUsuario.RESPONSAVEL_CONSULADO})

    def validar_criacao(self, usuario: Usuario) -> None:
        if usuario.is_admin:
            return
        if usuario.tipo_usuario not in self.PAPEIS_SOLICITANTES:
            raise PermissaoNegadaError("Seu perfil de usuário não pode solicitar o cadastro de consulados.")
        if self.repositorio.existe(responsavel=usuario, status_aprovacao=StatusAprovacao.PENDENTE):
            raise ConflitoError(
                "Você já tem uma solicitação de consulado em análise. Aguarde a resposta da administração."
            )

    @transaction.atomic
    def criar_consulado(self, usuario: Usuario, *, foto: File | None = None, **dados: Any) -> Consulado:
        """Cria o consulado; ``foto`` (imagem do local enviada pelo solicitante) vira a capa da galeria."""
        self.validar_criacao(usuario)
        if not (dados.get("link_whatsapp") or "").strip():
            raise RegraNegocioError("Informe o link do grupo do WhatsApp do consulado.", campo="link_whatsapp")
        # Cadastros feitos por admin já nascem aprovados; os demais são solicitações.
        status = StatusAprovacao.APROVADO if usuario.is_admin else StatusAprovacao.PENDENTE
        consulado = self.repositorio.criar(responsavel=usuario, status_aprovacao=status, **dados)
        # O responsável é automaticamente membro do próprio consulado.
        self.membro_repositorio.obter_ou_criar(usuario, consulado)
        if foto:
            consulado.fotos.create(imagem=foto, legenda="Foto do local", ordem=0)
        return consulado

    # ------------------------------------------------------------ moderação
    @transaction.atomic
    def aprovar_solicitacao(self, consulado: Consulado, *, moderador: Usuario) -> Consulado:
        AprovacaoService().aprovar(consulado, moderador=moderador)
        if consulado.motivo_rejeicao:
            self.repositorio.atualizar(consulado, motivo_rejeicao="")
        # O torcedor que teve o consulado aceito vira embaixador.
        responsavel = consulado.responsavel
        if responsavel.tipo_usuario == TipoUsuario.TORCEDOR:
            self.usuario_repositorio.atualizar(responsavel, tipo_usuario=TipoUsuario.RESPONSAVEL_CONSULADO)
        return consulado

    @transaction.atomic
    def rejeitar_solicitacao(self, consulado: Consulado, *, moderador: Usuario, motivo: str = "") -> Consulado:
        AprovacaoService().rejeitar(consulado, moderador=moderador)
        return self.repositorio.atualizar(consulado, motivo_rejeicao=motivo.strip())

    # -------------------------------------------------------------- membros
    @staticmethod
    def exigir_gestor(usuario: Usuario, consulado: Consulado) -> None:
        if not (usuario.is_admin or consulado.responsavel_id == usuario.id):
            raise PermissaoNegadaError("Apenas o embaixador do consulado pode gerenciar seus membros.")

    @transaction.atomic
    def cadastrar_membro(
        self, gestor: Usuario, consulado: Consulado, *, email: str, nome: str = "", cargo: str = "",
    ) -> tuple[MembroConsulado, str | None]:
        """
        Filia um usuário ao consulado pelo e-mail.

        Se ainda não houver conta com o e-mail, cria uma conta de torcedor e
        devolve a senha provisória para o embaixador repassar ao novo membro.
        """
        self.exigir_gestor(gestor, consulado)
        email = email.strip().lower()
        usuario = self.usuario_repositorio.get_queryset().filter(email__iexact=email).first()
        senha_provisoria = None
        if usuario is None:
            if not nome.strip():
                raise RegraNegocioError("Informe o nome para cadastrar um novo torcedor.", campo="nome")
            senha_provisoria = secrets.token_urlsafe(9)
            usuario = self.usuario_repositorio.criar_usuario(
                email=email, password=senha_provisoria, nome=nome.strip(), tipo_usuario=TipoUsuario.TORCEDOR,
            )
        elif self.membro_repositorio.eh_membro(usuario, consulado.id):
            raise ConflitoError(f"{usuario.nome} já é membro deste consulado.", campo="email")

        membro, _ = self.membro_repositorio.obter_ou_criar(usuario, consulado)
        # Se a pessoa já tinha pedido para entrar, o pedido fica atendido.
        pedido = self.solicitacao_repositorio.pendente(usuario, consulado)
        if pedido:
            self._responder(pedido, gestor, StatusAprovacao.APROVADO)
        if cargo.strip():
            membro = self.membro_repositorio.atualizar(membro, cargo=cargo.strip())
        return membro, senha_provisoria

    def definir_cargo(self, gestor: Usuario, membro: MembroConsulado, cargo: str) -> MembroConsulado:
        self.exigir_gestor(gestor, membro.consulado)
        return self.membro_repositorio.atualizar(membro, cargo=cargo.strip())

    def remover_membro(self, gestor: Usuario, membro: MembroConsulado) -> None:
        self.exigir_gestor(gestor, membro.consulado)
        if membro.usuario_id == membro.consulado.responsavel_id:
            raise RegraNegocioError("O embaixador não pode ser removido do próprio consulado.")
        self.membro_repositorio.remover(membro)

    def sair_do_consulado(self, usuario: Usuario, consulado: Consulado) -> None:
        if consulado.responsavel_id == usuario.id:
            raise RegraNegocioError("O embaixador não pode deixar o próprio consulado.")
        if not self.membro_repositorio.remover_filiacao(usuario, consulado):
            raise RecursoNaoEncontradoError("Você não é membro deste consulado.")

    # ------------------------------------------------ solicitações de entrada
    def solicitar_entrada(self, usuario: Usuario, consulado: Consulado) -> SolicitacaoMembro:
        if not consulado.aprovado:
            raise RegraNegocioError("Este consulado ainda não foi aprovado pela administração.")
        if self.membro_repositorio.eh_membro(usuario, consulado.id):
            raise ConflitoError("Você já é membro deste consulado.")
        if self.solicitacao_repositorio.pendente(usuario, consulado):
            raise ConflitoError("Você já pediu para entrar neste consulado. Aguarde a resposta do embaixador.")
        return self.solicitacao_repositorio.criar(usuario=usuario, consulado=consulado)

    def cancelar_solicitacao(self, usuario: Usuario, solicitacao: SolicitacaoMembro) -> None:
        if solicitacao.usuario_id != usuario.id:
            raise PermissaoNegadaError("Você só pode cancelar os seus próprios pedidos.")
        if solicitacao.status_aprovacao != StatusAprovacao.PENDENTE:
            raise RegraNegocioError("Este pedido já foi respondido pelo embaixador.")
        self.solicitacao_repositorio.remover(solicitacao)

    def _responder(self, solicitacao: SolicitacaoMembro, gestor: Usuario, status: str) -> SolicitacaoMembro:
        return self.solicitacao_repositorio.atualizar(
            solicitacao, status_aprovacao=status, respondido_em=timezone.now(), respondido_por=gestor,
        )

    @transaction.atomic
    def responder_solicitacao(self, gestor: Usuario, solicitacao: SolicitacaoMembro, *, aprovar: bool) -> SolicitacaoMembro:
        self.exigir_gestor(gestor, solicitacao.consulado)
        if solicitacao.status_aprovacao != StatusAprovacao.PENDENTE:
            raise RegraNegocioError("Este pedido já foi respondido.")
        if aprovar:
            self.membro_repositorio.obter_ou_criar(solicitacao.usuario, solicitacao.consulado)
        return self._responder(solicitacao, gestor, StatusAprovacao.APROVADO if aprovar else StatusAprovacao.REJEITADO)

    # ------------------------------------------------------------- WhatsApp
    def pode_ver_whatsapp(self, usuario: Usuario, consulado: Consulado) -> bool:
        """O link do grupo é só para membros do consulado (e para o embaixador e o admin)."""
        if usuario.is_admin or consulado.responsavel_id == usuario.id:
            return True
        eh_membro = getattr(consulado, "eh_membro", None)  # anotado pelo repositório, quando disponível
        if eh_membro is not None:
            return bool(eh_membro)
        return self.membro_repositorio.eh_membro(usuario, consulado.id)

    # ---------------------------------------------------------------- fotos
    MAXIMO_FOTOS = 10

    def pode_editar_fotos(self, usuario: Usuario, consulado: Consulado) -> bool:
        """Embaixador do consulado ou membro com cargo atribuído pelo embaixador."""
        return consulado.responsavel_id == usuario.id or self.membro_repositorio.tem_cargo(usuario, consulado.id)

    def exigir_editor_de_fotos(self, usuario: Usuario, consulado: Consulado) -> None:
        if not self.pode_editar_fotos(usuario, consulado):
            raise PermissaoNegadaError(
                "Apenas o embaixador e os membros com cargo no consulado podem editar as fotos."
            )

    @transaction.atomic
    def adicionar_foto(self, usuario: Usuario, consulado: Consulado, *, imagem: File, legenda: str = "") -> FotoConsulado:
        self.exigir_editor_de_fotos(usuario, consulado)
        fotos = self.foto_repositorio.do_consulado(consulado)
        if fotos.count() >= self.MAXIMO_FOTOS:
            raise RegraNegocioError(
                f"O consulado já tem {self.MAXIMO_FOTOS} fotos, o máximo permitido. Remova uma para enviar outra.",
                campo="imagem",
            )
        ultima = fotos.last()
        return self.foto_repositorio.criar(
            consulado=consulado, imagem=imagem, legenda=legenda.strip(), ordem=(ultima.ordem + 1) if ultima else 0,
        )

    def editar_legenda(self, usuario: Usuario, foto: FotoConsulado, legenda: str) -> FotoConsulado:
        self.exigir_editor_de_fotos(usuario, foto.consulado)
        return self.foto_repositorio.atualizar(foto, legenda=legenda.strip())

    @transaction.atomic
    def definir_capa(self, usuario: Usuario, foto: FotoConsulado) -> None:
        """A capa é a primeira foto da galeria (e a que aparece no resumo do mapa)."""
        self.exigir_editor_de_fotos(usuario, foto.consulado)
        outras = [f for f in self.foto_repositorio.do_consulado(foto.consulado) if f.pk != foto.pk]
        for posicao, item in enumerate([foto, *outras]):
            if item.ordem != posicao:
                self.foto_repositorio.atualizar(item, ordem=posicao)

    def remover_foto(self, usuario: Usuario, foto: FotoConsulado) -> None:
        self.exigir_editor_de_fotos(usuario, foto.consulado)
        arquivo = foto.imagem.name
        self.foto_repositorio.remover(foto)
        if arquivo:
            transaction.on_commit(lambda: foto.imagem.storage.delete(arquivo))
