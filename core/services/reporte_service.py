"""
Reportes de problemas e sugestões.

* Qualquer usuário logado envia; só administradores veem e respondem.
* O admin marca como resolvido (ou reabre).
"""
from __future__ import annotations

from django.core.files import File
from django.db.models import QuerySet
from django.utils import timezone

from core.exceptions import PermissaoNegadaError, RegraNegocioError
from core.models import Reporte, Usuario


class ReporteService:
    @staticmethod
    def _exigir_admin(usuario: Usuario) -> None:
        if not usuario.is_admin:
            raise PermissaoNegadaError("Apenas administradores veem os reportes.")

    def enviar(
        self, usuario: Usuario, *, tipo: str, mensagem: str, pagina: str = "", captura: File | None = None,
    ) -> Reporte:
        mensagem = mensagem.strip()
        if len(mensagem) < 10:
            raise RegraNegocioError("Conte com um pouco mais de detalhe (pelo menos 10 caracteres).", campo="mensagem")
        return Reporte.objects.create(
            usuario=usuario, tipo=tipo, mensagem=mensagem, pagina=pagina[:300], captura=captura or "",
        )

    def listar(self, admin: Usuario) -> QuerySet[Reporte]:
        self._exigir_admin(admin)
        return Reporte.objects.select_related("usuario", "resolvido_por")

    def marcar_resolvido(self, admin: Usuario, reporte: Reporte) -> Reporte:
        self._exigir_admin(admin)
        reporte.status, reporte.resolvido_em, reporte.resolvido_por = Reporte.Status.RESOLVIDO, timezone.now(), admin
        reporte.save(update_fields=["status", "resolvido_em", "resolvido_por"])
        return reporte

    def reabrir(self, admin: Usuario, reporte: Reporte) -> Reporte:
        self._exigir_admin(admin)
        reporte.status, reporte.resolvido_em, reporte.resolvido_por = Reporte.Status.ABERTO, None, None
        reporte.save(update_fields=["status", "resolvido_em", "resolvido_por"])
        return reporte
