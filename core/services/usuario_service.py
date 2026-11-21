"""
Regras de negócio da conta do usuário.

* Auto-cadastro: o papel ADMIN nunca pode ser escolhido e o e-mail é único.
* Perfil ("Minha conta"): nome, data de nascimento e e-mail são obrigatórios;
  telefone, CPF e endereço são opcionais. O e-mail (usado no login) e o CPF
  não podem repetir os de outra conta.
* Foto do perfil: opcional; pode ser enviada, trocada e removida. O arquivo
  antigo é apagado do armazenamento.
* Troca de senha: exige a senha atual. Trocar (ou redefinir) a senha encerra
  as sessões do aplicativo (tokens JWT), que precisam entrar de novo.
"""
from __future__ import annotations

from datetime import date
from typing import Any

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.files import File
from django.core.validators import validate_email
from django.db import transaction
from django.utils import timezone

from core.exceptions import ConflitoError, PermissaoNegadaError, RegraNegocioError
from core.models import TipoUsuario, Usuario
from core.repositories import TokenWhitelistRepository, UsuarioRepository
from core.validators import somente_digitos, validar_cpf, validar_telefone

IDADE_MAXIMA = 120


class UsuarioService:
    # Papéis que podem ser escolhidos no auto-cadastro (ADMIN nunca).
    PAPEIS_AUTOCADASTRO = frozenset({
        TipoUsuario.TORCEDOR,
        TipoUsuario.RESPONSAVEL_CONSULADO,
        TipoUsuario.RESPONSAVEL_ALIADO,
    })

    def __init__(self, repositorio: UsuarioRepository | None = None) -> None:
        self.repositorio = repositorio or UsuarioRepository()

    # ------------------------------------------------------------- cadastro
    def validar_registro(self, *, email: str, tipo_usuario: str) -> None:
        if tipo_usuario not in self.PAPEIS_AUTOCADASTRO:
            raise PermissaoNegadaError("Tipo de usuário não permitido no cadastro.", campo="tipo_usuario")
        if self.repositorio.email_em_uso(email):
            raise ConflitoError("Já existe um usuário com este e-mail.", campo="email")

    @transaction.atomic
    def registrar(self, *, email: str, password: str, **dados: Any) -> Usuario:
        dados.setdefault("tipo_usuario", TipoUsuario.TORCEDOR)
        self.validar_registro(email=email, tipo_usuario=dados["tipo_usuario"])
        return self.repositorio.criar_usuario(email=email, password=password, **dados)

    # --------------------------------------------------------------- perfil
    @staticmethod
    def _validar(validador, valor: str, campo: str) -> None:
        try:
            validador(valor)
        except ValidationError as erro:
            raise RegraNegocioError(erro.messages[0], campo=campo) from erro

    def validar_data_nascimento(self, data: date | None) -> None:
        if data is None:
            raise RegraNegocioError("Informe a sua data de nascimento.", campo="data_nascimento")
        hoje = timezone.localdate()
        if data >= hoje:
            raise RegraNegocioError("A data de nascimento precisa estar no passado.", campo="data_nascimento")
        if hoje.year - data.year > IDADE_MAXIMA:
            raise RegraNegocioError("Confira o ano da data de nascimento.", campo="data_nascimento")

    def normalizar_cpf(self, usuario: Usuario, cpf: str | None) -> str | None:
        """Devolve o CPF só com dígitos (ou None se vazio), já validado e sem repetir o de outra conta."""
        cpf = somente_digitos(cpf)
        if not cpf:
            return None
        self._validar(validar_cpf, cpf, "cpf")
        if self.repositorio.cpf_em_uso(cpf, exceto_id=usuario.id):
            raise ConflitoError("Este CPF já está cadastrado em outra conta.", campo="cpf")
        return cpf

    @transaction.atomic
    def atualizar_perfil(
        self,
        usuario: Usuario,
        *,
        nome: str,
        email: str,
        data_nascimento: date | None,
        telefone: str = "",
        cpf: str | None = "",
        endereco: str = "",
        mostrar_aniversario: bool | None = None,
    ) -> Usuario:
        nome = (nome or "").strip()
        if not nome:
            raise RegraNegocioError("Informe o seu nome.", campo="nome")
        email = (email or "").strip().lower()
        if not email:
            raise RegraNegocioError("Informe o seu e-mail.", campo="email")
        self._validar(validate_email, email, "email")
        if self.repositorio.email_em_uso(email, exceto_id=usuario.id):
            raise ConflitoError("Já existe outra conta com este e-mail.", campo="email")
        self.validar_data_nascimento(data_nascimento)
        telefone = (telefone or "").strip()
        if telefone:
            self._validar(validar_telefone, telefone, "telefone")
        return self.repositorio.atualizar(
            usuario,
            nome=nome,
            email=email,
            data_nascimento=data_nascimento,
            telefone=telefone,
            cpf=self.normalizar_cpf(usuario, cpf),
            endereco=(endereco or "").strip(),
            **({} if mostrar_aniversario is None else {"mostrar_aniversario": bool(mostrar_aniversario)}),
        )

    # ----------------------------------------------------------------- foto
    @staticmethod
    def _apagar_arquivo(usuario: Usuario, nome: str) -> None:
        """Apaga o arquivo só depois de a transação ser confirmada (nada se perde se der erro)."""
        if nome:
            armazenamento = usuario.foto.storage
            transaction.on_commit(lambda: armazenamento.delete(nome))

    @transaction.atomic
    def definir_foto(self, usuario: Usuario, arquivo: File) -> Usuario:
        """Envia a foto do perfil (ou troca a atual, apagando o arquivo antigo)."""
        anterior = usuario.foto.name if usuario.foto else ""
        usuario = self.repositorio.atualizar(usuario, foto=arquivo)
        self._apagar_arquivo(usuario, anterior)
        return usuario

    @transaction.atomic
    def remover_foto(self, usuario: Usuario) -> Usuario:
        if not usuario.foto:
            raise RegraNegocioError("Você não tem foto no perfil.")
        anterior = usuario.foto.name
        usuario = self.repositorio.atualizar(usuario, foto="")
        self._apagar_arquivo(usuario, anterior)
        return usuario

    # ------------------------------------------- gestão pelo administrador
    @staticmethod
    def _exigir_gestao(admin: Usuario, usuario: Usuario) -> None:
        if not admin.is_admin:
            raise PermissaoNegadaError("Apenas administradores gerenciam as contas dos usuários.")
        if admin.pk == usuario.pk:
            raise RegraNegocioError("Você não pode alterar o papel nem o acesso da sua própria conta.")
        if usuario.is_superuser and not admin.is_superuser:
            raise PermissaoNegadaError("Esta conta só pode ser alterada por um superusuário.")

    @transaction.atomic
    def definir_papel(self, admin: Usuario, usuario: Usuario, tipo_usuario: str) -> Usuario:
        """Troca o papel da conta (torcedor, embaixador, lojista ou administrador)."""
        self._exigir_gestao(admin, usuario)
        if tipo_usuario not in TipoUsuario.values:
            raise RegraNegocioError("Papel inválido.", campo="tipo_usuario")
        if usuario.tipo_usuario == tipo_usuario:
            raise RegraNegocioError("A conta já tem este papel.", codigo="status_inalterado")
        return self.repositorio.atualizar(usuario, tipo_usuario=tipo_usuario)

    @transaction.atomic
    def definir_ativo(self, admin: Usuario, usuario: Usuario, ativo: bool) -> Usuario:
        """Bloqueia ou libera o acesso da conta. Bloquear encerra as sessões do aplicativo."""
        self._exigir_gestao(admin, usuario)
        if usuario.is_active == ativo:
            raise RegraNegocioError("A conta já está neste estado.", codigo="status_inalterado")
        usuario = self.repositorio.atualizar(usuario, is_active=ativo)
        if not ativo:
            self.encerrar_sessoes_do_app(usuario)
        return usuario

    # ---------------------------------------------------------------- senha
    @staticmethod
    def validar_nova_senha(usuario: Usuario, senha: str) -> None:
        try:
            validate_password(senha, user=usuario)
        except ValidationError as erro:
            raise RegraNegocioError(" ".join(erro.messages), campo="nova_senha") from erro

    @staticmethod
    def encerrar_sessoes_do_app(usuario: Usuario) -> None:
        """Tira da whitelist os tokens JWT do usuário: o aplicativo precisa entrar de novo."""
        TokenWhitelistRepository().remover_todos_do_usuario(usuario.id)

    @transaction.atomic
    def trocar_senha(self, usuario: Usuario, *, senha_atual: str, nova_senha: str) -> Usuario:
        if not usuario.check_password(senha_atual):
            raise RegraNegocioError("A senha atual não confere.", campo="senha_atual")
        if senha_atual == nova_senha:
            raise RegraNegocioError("A nova senha precisa ser diferente da atual.", campo="nova_senha")
        self.validar_nova_senha(usuario, nova_senha)
        usuario.set_password(nova_senha)
        usuario.save(update_fields=["password"])
        self.encerrar_sessoes_do_app(usuario)
        return usuario
