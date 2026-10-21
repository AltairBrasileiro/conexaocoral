"""Tradução das exceções de domínio para respostas HTTP padronizadas."""
from __future__ import annotations

import logging
from typing import Any

from rest_framework.response import Response
from rest_framework.settings import api_settings
from rest_framework.views import exception_handler

from core.exceptions import RegraNegocioError

logger = logging.getLogger(__name__)


def custom_exception_handler(exc: Exception, context: dict[str, Any]) -> Response | None:
    """
    * ``RegraNegocioError`` (e subclasses) -> status definido na exceção.
    * Demais exceções -> handler padrão do DRF.
    """
    if isinstance(exc, RegraNegocioError):
        campo = exc.campo or api_settings.NON_FIELD_ERRORS_KEY
        logger.info("Regra de negócio violada: %s (%s)", exc.mensagem, exc.codigo)
        return Response({"codigo": exc.codigo, "detail": exc.mensagem, "erros": {campo: [exc.mensagem]}},
                        status=exc.status_code)
    return exception_handler(exc, context)
