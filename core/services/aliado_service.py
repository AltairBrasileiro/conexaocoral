"""
Regras de negócio dos aliados (negócios de torcedores na Vitrine da Torcida).

* Qualquer usuário pode cadastrar o próprio negócio; o cadastro nasce PENDENTE
  e só aparece na vitrine depois que o administrador aprova. Cadastros feitos
  pelo administrador já nascem aprovados.
* Ao aprovar o negócio de um torcedor, ele passa a ser Responsável por Aliado
  (lojista).
* O dono edita e exclui o próprio negócio. Depois de aprovado, ele edita com
  autonomia: o negócio continua na vitrine (e com o selo). Só a correção de um
  cadastro recusado volta para a moderação.
* A foto do negócio e a foto de perfil são opcionais; ao trocar, remover ou
  excluir o cadastro, o arquivo antigo é apagado do armazenamento.
"""
from __future__ import annotations

from typing import Any

from django.db import transaction

from core.exceptions import ConflitoError, PermissaoNegadaError, RegraNegocioError
from core.models import Aliado, StatusAprovacao, TipoUsuario, Usuario
from core.repositories import AliadoRepository, UsuarioRepository
from core.services.aprovacao_service import AprovacaoService


class AliadoService:
    # Evita que uma mesma conta encha a fila de moderação.
    MAXIMO_POR_USUARIO = 5
    CAMPOS_IMAGEM = ("foto", "foto_perfil")

    def __init__(self, repositorio: AliadoRepository | None = None) -> None:
        self.repositorio = repositorio or AliadoRepository()

    # ------------------------------------------------------------- cadastro
    def validar_criacao(self, usuario: Usuario) -> None:
        if usuario.is_admin:
            return
        if self.repositorio.listar(usuario=usuario).count() >= self.MAXIMO_POR_USUARIO:
            raise ConflitoError(
                f"Cada conta pode cadastrar até {self.MAXIMO_POR_USUARIO} negócios. Exclua um para cadastrar outro."
            )

    @staticmethod
    def _validar_dados(dados: dict[str, Any]) -> None:
        if "nome_negocio" in dados:
            dados["nome_negocio"] = (dados["nome_negocio"] or "").strip()
            if not dados["nome_negocio"]:
                raise RegraNegocioError("Informe o nome do negócio.", campo="nome_negocio")
        if "descricao" in dados:
            dados["descricao"] = (dados["descricao"] or "").strip()

    @staticmethod
    def exigir_dono(usuario: Usuario, aliado: Aliado) -> None:
        if not (usuario.is_admin or aliado.usuario_id == usuario.id):
            raise PermissaoNegadaError("Você só pode alterar os negócios que cadastrou.")

    @staticmethod
    def _apagar_arquivos(aliado: Aliado, nomes: list[str]) -> None:
        """Apaga os arquivos só depois de a transação ser confirmada."""
        armazenamento = aliado.foto.storage
        for nome in filter(None, nomes):
            transaction.on_commit(lambda nome=nome: armazenamento.delete(nome))

    @transaction.atomic
    def criar_aliado(self, usuario: Usuario, **dados: Any) -> Aliado:
        self.validar_criacao(usuario)
        self._validar_dados(dados)
        for campo in self.CAMPOS_IMAGEM:
            if not dados.get(campo):
                dados.pop(campo, None)
        status = StatusAprovacao.APROVADO if usuario.is_admin else StatusAprovacao.PENDENTE
        return self.repositorio.criar(usuario=usuario, status_aprovacao=status, **dados)

    @transaction.atomic
    def atualizar_aliado(
        self, aliado: Aliado, usuario: Usuario, *, remover_foto: bool = False, remover_foto_perfil: bool = False,
        **dados: Any,
    ) -> Aliado:
        """
        Atualiza os dados informados. ``foto``/``foto_perfil`` com um arquivo
        trocam a imagem; ``remover_foto``/``remover_foto_perfil`` apagam a atual.
        """
        self.exigir_dono(usuario, aliado)
        self._validar_dados(dados)
        remover = {"foto": remover_foto, "foto_perfil": remover_foto_perfil}
        anteriores = []
        for campo in self.CAMPOS_IMAGEM:
            atual = getattr(aliado, campo)
            if dados.get(campo):
                anteriores.append(atual.name if atual else "")
            else:
                dados.pop(campo, None)
                if remover[campo] and atual:
                    anteriores.append(atual.name)
                    dados[campo] = ""
        # Cadastro recusado que o dono corrige é reenviado para a moderação.
        if not usuario.is_admin and dados and aliado.status_aprovacao == StatusAprovacao.REJEITADO:
            dados.update(status_aprovacao=StatusAprovacao.PENDENTE, motivo_rejeicao="")
        aliado = self.repositorio.atualizar(aliado, **dados)
        self._apagar_arquivos(aliado, anteriores)
        return aliado

    @transaction.atomic
    def excluir_aliado(self, aliado: Aliado, usuario: Usuario) -> None:
        self.exigir_dono(usuario, aliado)
        self._apagar_arquivos(aliado, [getattr(aliado, c).name for c in self.CAMPOS_IMAGEM if getattr(aliado, c)])
        self.repositorio.remover(aliado)

    # ------------------------------------------------------------ moderação
    @transaction.atomic
    def aprovar(self, aliado: Aliado, *, moderador: Usuario) -> Aliado:
        AprovacaoService().aprovar(aliado, moderador=moderador)
        if aliado.motivo_rejeicao:
            self.repositorio.atualizar(aliado, motivo_rejeicao="")
        # O torcedor que teve o negócio aceito vira lojista.
        dono = aliado.usuario
        if dono.tipo_usuario == TipoUsuario.TORCEDOR:
            UsuarioRepository().atualizar(dono, tipo_usuario=TipoUsuario.RESPONSAVEL_ALIADO)
        return aliado

    @transaction.atomic
    def rejeitar(self, aliado: Aliado, *, moderador: Usuario, motivo: str = "") -> Aliado:
        AprovacaoService().rejeitar(aliado, moderador=moderador)
        return self.repositorio.atualizar(aliado, motivo_rejeicao=motivo.strip())

    def definir_selo(self, aliado: Aliado, *, verificado: bool, moderador: Usuario) -> Aliado:
        if not moderador.is_admin:
            raise PermissaoNegadaError("Apenas administradores podem gerenciar o selo de verificado.")
        if verificado and not aliado.aprovado:
            raise RegraNegocioError("Só aliados aprovados podem receber o selo de verificado.")
        if aliado.selo_verificado == verificado:
            raise RegraNegocioError("O selo já está neste estado.", codigo="status_inalterado")
        return self.repositorio.atualizar(aliado, selo_verificado=verificado)
