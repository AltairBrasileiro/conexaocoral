"""
Exceções de domínio.

A camada de serviços lança estas exceções sem depender do DRF. A tradução
para respostas HTTP fica no ``custom_exception_handler`` (camada de views) e
no ``ValidacaoServiceMixin`` (camada de serializers).
"""
from __future__ import annotations


class RegraNegocioError(Exception):
    """Violação de regra de negócio (HTTP 400 por padrão)."""

    status_code: int = 400
    codigo_padrao: str = "regra_negocio"

    def __init__(self, mensagem: str, *, campo: str | None = None, codigo: str | None = None) -> None:
        super().__init__(mensagem)
        self.mensagem = mensagem
        self.campo = campo
        self.codigo = codigo or self.codigo_padrao

    def __str__(self) -> str:
        return self.mensagem


class ConflitoError(RegraNegocioError):
    """Recurso duplicado ou em conflito com o estado atual (HTTP 409)."""

    status_code = 409
    codigo_padrao = "conflito"


class PermissaoNegadaError(RegraNegocioError):
    """Usuário autenticado, mas sem direito à operação (HTTP 403)."""

    status_code = 403
    codigo_padrao = "permissao_negada"


class RecursoNaoEncontradoError(RegraNegocioError):
    """Recurso inexistente (HTTP 404)."""

    status_code = 404
    codigo_padrao = "nao_encontrado"
