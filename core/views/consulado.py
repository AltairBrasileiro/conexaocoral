from __future__ import annotations

from django.db.models import QuerySet
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from core.filters import ConsuladoFilter
from core.models import Consulado
from core.permissions import IsAdministrador, IsDonoOuAdmin
from core.exceptions import RegraNegocioError
from core.repositories import ConsuladoRepository, MembroConsuladoRepository, SolicitacaoMembroRepository
from core.serializers import ConsuladoSerializer, MembroConsuladoSerializer, SolicitacaoMembroSerializer
from core.services import ConsuladoService
from core.views.mixins import PermissaoPorAcaoMixin


class ConsuladoViewSet(PermissaoPorAcaoMixin, viewsets.ModelViewSet):
    """
    CRUD de consulados.

    * Listar/detalhar: qualquer autenticado (vê aprovados + os que administra).
    * Criar: torcedor ou responsável solicita (nasce PENDENTE); admin cria aprovado.
    * Editar/excluir: dono ou admin.
    * Aprovar/rejeitar: admin. Aprovar torna o solicitante torcedor embaixador;
      rejeitar aceita um ``motivo`` opcional.
    * Entrada de membros: o torcedor pede (``solicitar-entrada``) e o embaixador
      lista (``solicitacoes-entrada``) e responde (``responder-entrada``).
    """

    serializer_class = ConsuladoSerializer
    filterset_class = ConsuladoFilter
    search_fields = ("nome", "endereco", "descricao")
    ordering_fields = ("nome", "criado_em", "total_membros")
    # Explícito: consultas com Count (total_membros) ignoram o Meta.ordering do model.
    ordering = ("nome",)
    campo_dono = "responsavel_id"

    permission_classes = (IsAuthenticated,)
    # "create" usa a permissão padrão: quem pode solicitar é decidido pelo ConsuladoService.
    permission_classes_por_acao = {
        "update": [IsDonoOuAdmin],
        "partial_update": [IsDonoOuAdmin],
        "destroy": [IsDonoOuAdmin],
        "membros": [IsDonoOuAdmin],
        "solicitacoes_entrada": [IsDonoOuAdmin],
        "responder_entrada": [IsDonoOuAdmin],
        "aprovar": [IsAdministrador],
        "rejeitar": [IsAdministrador],
    }

    service = ConsuladoService()

    def get_queryset(self) -> QuerySet[Consulado]:
        if getattr(self, "swagger_fake_view", False):  # geração do schema OpenAPI
            return Consulado.objects.none()
        return ConsuladoRepository().visiveis_para(self.request.user)

    def perform_create(self, serializer: ConsuladoSerializer) -> None:
        serializer.instance = self.service.criar_consulado(self.request.user, **serializer.validated_data)

    @action(detail=True, methods=["post"])
    def aprovar(self, request: Request, pk: str | None = None) -> Response:
        consulado = self.service.aprovar_solicitacao(self.get_object(), moderador=request.user)
        return Response(self.get_serializer(consulado).data)

    @action(detail=True, methods=["post"])
    def rejeitar(self, request: Request, pk: str | None = None) -> Response:
        consulado = self.service.rejeitar_solicitacao(
            self.get_object(), moderador=request.user, motivo=str(request.data.get("motivo", "")),
        )
        return Response(self.get_serializer(consulado).data)

    @action(detail=True, methods=["get"], serializer_class=MembroConsuladoSerializer)
    def membros(self, request: Request, pk: str | None = None) -> Response:
        """Lista paginada de membros (apenas responsável ou admin)."""
        consulado = self.get_object()
        qs = MembroConsuladoRepository().membros_do_consulado(consulado)
        pagina = self.paginate_queryset(qs)
        serializer = self.get_serializer(pagina if pagina is not None else qs, many=True)
        return self.get_paginated_response(serializer.data) if pagina is not None else Response(serializer.data)

    @action(detail=True, methods=["post"])
    def sair(self, request: Request, pk: str | None = None) -> Response:
        """O usuário logado deixa de ser membro do consulado."""
        self.service.sair_do_consulado(request.user, self.get_object())
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["post"], url_path="solicitar-entrada", serializer_class=SolicitacaoMembroSerializer)
    def solicitar_entrada(self, request: Request, pk: str | None = None) -> Response:
        """O usuário logado pede para ser membro (o embaixador aprova)."""
        solicitacao = self.service.solicitar_entrada(request.user, self.get_object())
        return Response(SolicitacaoMembroSerializer(solicitacao).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["get"], url_path="solicitacoes-entrada", serializer_class=SolicitacaoMembroSerializer)
    def solicitacoes_entrada(self, request: Request, pk: str | None = None) -> Response:
        """Pedidos de entrada aguardando resposta (apenas embaixador ou admin)."""
        pedidos = SolicitacaoMembroRepository().pendentes_do_consulado(self.get_object())
        return Response(SolicitacaoMembroSerializer(pedidos, many=True).data)

    @action(detail=True, methods=["post"], url_path="responder-entrada", serializer_class=SolicitacaoMembroSerializer)
    def responder_entrada(self, request: Request, pk: str | None = None) -> Response:
        """Body: ``{"solicitacao": <id>, "aprovar": true|false}``."""
        consulado = self.get_object()
        pedido_id = str(request.data.get("solicitacao", ""))
        pedido = (
            SolicitacaoMembroRepository().pendentes_do_consulado(consulado).filter(pk=pedido_id).first()
            if pedido_id.isdigit() else None
        )
        if pedido is None:
            raise RegraNegocioError("Pedido de entrada não encontrado.", campo="solicitacao")
        aprovar = str(request.data.get("aprovar", "")).lower() in ("1", "true", "sim")
        pedido = self.service.responder_solicitacao(request.user, pedido, aprovar=aprovar)
        return Response(SolicitacaoMembroSerializer(pedido).data)
