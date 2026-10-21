"""Configuração do Django Admin."""
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.forms import UserChangeForm, UserCreationForm

from core.models import (
    Aliado,
    CheckIn,
    Consulado,
    Evento,
    FotoConsulado,
    MembroConsulado,
    Partida,
    PresencaEvento,
    StatusAprovacao,
    TokenWhitelist,
    Usuario,
)


class UsuarioCreationForm(UserCreationForm):
    """Formulário de criação sem o campo username do auth.User."""

    class Meta(UserCreationForm.Meta):
        model = Usuario
        fields = ("email", "nome", "tipo_usuario")
        field_classes = {}


class UsuarioChangeForm(UserChangeForm):
    class Meta(UserChangeForm.Meta):
        model = Usuario
        fields = "__all__"
        field_classes = {}


@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    """UserAdmin adaptado para login por e-mail (sem username/first/last name)."""

    form = UsuarioChangeForm
    add_form = UsuarioCreationForm

    ordering = ("nome",)
    list_display = ("nome", "email", "tipo_usuario", "is_active", "criado_em")
    list_filter = ("tipo_usuario", "is_active", "is_staff")
    search_fields = ("nome", "email")
    readonly_fields = ("criado_em", "last_login")
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Dados pessoais", {"fields": ("nome", "telefone", "tipo_usuario")}),
        ("Permissões", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        ("Datas", {"fields": ("last_login", "criado_em")}),
    )
    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("email", "nome", "tipo_usuario", "password1", "password2"),
        }),
    )


@admin.action(description="Aprovar selecionados")
def aprovar(modeladmin, request, queryset):
    queryset.update(status_aprovacao=StatusAprovacao.APROVADO)


@admin.action(description="Rejeitar selecionados")
def rejeitar(modeladmin, request, queryset):
    fields = {"status_aprovacao": StatusAprovacao.REJEITADO}
    if queryset.model is Aliado:
        fields["selo_verificado"] = False  # respeita a CheckConstraint do selo
    queryset.update(**fields)


class MembroInline(admin.TabularInline):
    model = MembroConsulado
    extra = 0
    raw_id_fields = ("usuario",)
    readonly_fields = ("data_filiacao",)


class FotoInline(admin.TabularInline):
    model = FotoConsulado
    extra = 1


@admin.register(Consulado)
class ConsuladoAdmin(admin.ModelAdmin):
    list_display = ("nome", "responsavel", "status_aprovacao", "criado_em")
    list_filter = ("status_aprovacao",)
    search_fields = ("nome", "endereco")
    raw_id_fields = ("responsavel",)
    actions = (aprovar, rejeitar)
    inlines = (FotoInline, MembroInline)


@admin.register(Partida)
class PartidaAdmin(admin.ModelAdmin):
    list_display = ("adversario", "mando_campo", "campeonato", "data_hora")
    list_filter = ("mando_campo", "campeonato")
    date_hierarchy = "data_hora"


@admin.register(CheckIn)
class CheckInAdmin(admin.ModelAdmin):
    list_display = ("usuario", "partida", "consulado", "ativo", "data_checkin")
    list_filter = ("ativo",)
    raw_id_fields = ("usuario", "partida", "consulado")


@admin.register(Evento)
class EventoAdmin(admin.ModelAdmin):
    list_display = ("titulo", "consulado", "data_hora_inicio", "exclusivo_membros", "status_aprovacao")
    list_filter = ("status_aprovacao", "exclusivo_membros")
    search_fields = ("titulo",)
    actions = (aprovar, rejeitar)


@admin.register(PresencaEvento)
class PresencaEventoAdmin(admin.ModelAdmin):
    list_display = ("usuario", "evento", "data_confirmacao")
    raw_id_fields = ("usuario", "evento")


@admin.register(Aliado)
class AliadoAdmin(admin.ModelAdmin):
    list_display = ("nome_negocio", "categoria", "status_aprovacao", "selo_verificado")
    list_filter = ("status_aprovacao", "categoria", "selo_verificado")
    search_fields = ("nome_negocio",)
    actions = (aprovar, rejeitar)


@admin.register(TokenWhitelist)
class TokenWhitelistAdmin(admin.ModelAdmin):
    list_display = ("usuario", "tipo_token", "criado_em", "expira_em")
    list_filter = ("tipo_token",)
    search_fields = ("usuario__email", "jti")
    readonly_fields = ("usuario", "jti", "tipo_token", "criado_em", "expira_em")
