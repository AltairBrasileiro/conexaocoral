"""Model de usuário customizado (login por e-mail)."""
from __future__ import annotations

from typing import Any

from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models

from core.models.choices import TipoUsuario
from core.validators import validar_telefone


class UsuarioManager(BaseUserManager):
    """Manager que usa o e-mail como identificador único no lugar do username."""

    use_in_migrations = True

    def _create_user(self, email: str, password: str | None, **extra_fields: Any) -> "Usuario":
        if not email:
            raise ValueError("O e-mail é obrigatório.")
        email = self.normalize_email(email).lower()
        usuario = self.model(email=email, **extra_fields)
        usuario.set_password(password)  # set_password(None) gera senha inutilizável
        usuario.save(using=self._db)
        return usuario

    def create_user(self, email: str, password: str | None = None, **extra_fields: Any) -> "Usuario":
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        extra_fields.setdefault("tipo_usuario", TipoUsuario.TORCEDOR)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email: str, password: str | None = None, **extra_fields: Any) -> "Usuario":
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("tipo_usuario", TipoUsuario.ADMIN)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superusuário precisa de is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superusuário precisa de is_superuser=True.")
        return self._create_user(email, password, **extra_fields)


class Usuario(AbstractUser):
    """
    Usuário do sistema.

    Remove ``username``, ``first_name`` e ``last_name`` herdados de
    ``AbstractUser`` e usa ``nome`` + ``email`` (único, usado no login).
    """

    username = None
    first_name = None
    last_name = None

    nome = models.CharField("nome", max_length=150)
    email = models.EmailField("e-mail", unique=True)
    telefone = models.CharField("telefone", max_length=16, blank=True, validators=[validar_telefone])
    tipo_usuario = models.CharField(
        "tipo de usuário",
        max_length=25,
        choices=TipoUsuario.choices,
        default=TipoUsuario.TORCEDOR,
        db_index=True,
    )
    criado_em = models.DateTimeField("criado em", auto_now_add=True, editable=False)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["nome"]

    objects = UsuarioManager()

    class Meta:
        verbose_name = "usuário"
        verbose_name_plural = "usuários"
        ordering = ("nome",)

    def __str__(self) -> str:
        return f"{self.nome} <{self.email}>"

    # -- Compatibilidade com a API do AbstractUser ---------------------------
    def get_full_name(self) -> str:
        return self.nome

    def get_short_name(self) -> str:
        return self.nome.split()[0] if self.nome else self.email

    # -- Atalhos de papel (usados nas permissões e serviços) ----------------
    @property
    def is_admin(self) -> bool:
        return self.is_superuser or self.tipo_usuario == TipoUsuario.ADMIN

    @property
    def is_torcedor(self) -> bool:
        return self.tipo_usuario == TipoUsuario.TORCEDOR

    @property
    def is_responsavel_consulado(self) -> bool:
        return self.tipo_usuario == TipoUsuario.RESPONSAVEL_CONSULADO

    @property
    def is_responsavel_aliado(self) -> bool:
        return self.tipo_usuario == TipoUsuario.RESPONSAVEL_ALIADO
