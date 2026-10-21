"""Formulários da interface web."""
from __future__ import annotations

from datetime import timedelta

from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.utils import timezone

from core.models import Consulado


class EntrarForm(AuthenticationForm):
    """Login por e-mail (o ``USERNAME_FIELD`` do usuário é o e-mail)."""

    username = forms.EmailField(
        label="E-mail",
        widget=forms.EmailInput(attrs={"autofocus": True, "autocomplete": "email", "placeholder": "voce@email.com"}),
    )
    password = forms.CharField(
        label="Senha",
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}),
    )

    error_messages = {
        **AuthenticationForm.error_messages,
        "invalid_login": "E-mail ou senha incorretos.",
    }

    def clean_username(self) -> str:
        # O cadastro grava o e-mail em minúsculas (UsuarioManager).
        return self.cleaned_data["username"].strip().lower()


class ConsuladoForm(forms.ModelForm):
    """Dados operacionais que o responsável pode alterar."""

    class Meta:
        model = Consulado
        fields = ("endereco", "link_whatsapp", "descricao")
        labels = {
            "endereco": "Endereço",
            "link_whatsapp": "Link do grupo do WhatsApp",
            "descricao": "Descrição e funcionamento",
        }
        widgets = {
            "link_whatsapp": forms.URLInput(attrs={"placeholder": "https://chat.whatsapp.com/..."}),
            "descricao": forms.Textarea(attrs={"rows": 5, "placeholder": "Horários, telão, cardápio, avisos…"}),
        }


def _amanha_as_18h():
    return (timezone.localtime() + timedelta(days=1)).replace(hour=18, minute=0, second=0, microsecond=0)


class EventoForm(forms.Form):
    DURACOES = ((2, "2 horas"), (3, "3 horas"), (4, "4 horas"), (6, "6 horas"))

    titulo = forms.CharField(
        label="Título", max_length=150, widget=forms.TextInput(attrs={"placeholder": "Ex.: Resenha pré-jogo"}),
    )
    descricao = forms.CharField(label="Descrição", required=False, widget=forms.Textarea(attrs={"rows": 3}))
    inicio = forms.DateTimeField(
        label="Início",
        initial=_amanha_as_18h,
        input_formats=["%Y-%m-%dT%H:%M"],
        widget=forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
    )
    duracao = forms.TypedChoiceField(label="Duração", choices=DURACOES, coerce=int, initial=3)
    exclusivo_membros = forms.BooleanField(
        label="Exclusivo para membros",
        required=False,
        help_text="Só membros do consulado veem o evento.",
    )

    def dados_evento(self) -> dict:
        """Converte o formulário nos campos esperados por ``EventoService.criar_evento``."""
        inicio = self.cleaned_data["inicio"]
        return {
            "titulo": self.cleaned_data["titulo"].strip(),
            "descricao": self.cleaned_data["descricao"].strip(),
            "data_hora_inicio": inicio,
            "data_hora_fim": inicio + timedelta(hours=self.cleaned_data["duracao"]),
            "exclusivo_membros": self.cleaned_data["exclusivo_membros"],
        }
