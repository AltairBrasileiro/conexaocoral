"""Repositório genérico: encapsula o acesso ao ORM do Django."""
from __future__ import annotations

from typing import Any, Generic, TypeVar

from django.db import models
from django.db.models import QuerySet

ModelT = TypeVar("ModelT", bound=models.Model)


class BaseRepository(Generic[ModelT]):
    """
    Operações CRUD comuns.

    Subclasses definem ``model`` e acrescentam consultas específicas.
    Serviços dependem dos repositórios, nunca do ORM diretamente, o que
    facilita testes (basta injetar um repositório falso).
    """

    model: type[ModelT]

    def get_queryset(self) -> QuerySet[ModelT]:
        return self.model._default_manager.all()

    def obter_por_id(self, pk: Any) -> ModelT | None:
        return self.get_queryset().filter(pk=pk).first()

    def listar(self, **filtros: Any) -> QuerySet[ModelT]:
        return self.get_queryset().filter(**filtros)

    def existe(self, **filtros: Any) -> bool:
        return self.get_queryset().filter(**filtros).exists()

    def criar(self, **dados: Any) -> ModelT:
        return self.model._default_manager.create(**dados)

    def atualizar(self, instancia: ModelT, **dados: Any) -> ModelT:
        """Atualiza apenas os campos informados (``update_fields``)."""
        for campo, valor in dados.items():
            setattr(instancia, campo, valor)
        if dados:
            instancia.save(update_fields=list(dados))
        return instancia

    def remover(self, instancia: ModelT) -> None:
        instancia.delete()
