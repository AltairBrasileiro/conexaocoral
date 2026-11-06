"""Formulários da interface web."""
from __future__ import annotations

from datetime import timedelta

from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.core.files.uploadedfile import UploadedFile
from django.utils import timezone

from core.models import Consulado, Reporte
from core.validators import TAMANHO_MAXIMO_IMAGEM_MB, validar_extensao_imagem, validar_tamanho_imagem


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


class WhatsappObrigatorioMixin:
    """O grupo do WhatsApp é obrigatório: é por ele que a torcida chega ao consulado."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        campo = self.fields["link_whatsapp"]
        campo.required = True
        campo.error_messages["required"] = "Informe o link do grupo do WhatsApp do consulado."


class ConsuladoForm(WhatsappObrigatorioMixin, forms.ModelForm):
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


def _validar_upload_imagem(arquivo):
    """Valida só arquivos recém-enviados (a imagem já salva não é revalidada)."""
    if isinstance(arquivo, UploadedFile):
        validar_extensao_imagem(arquivo)
        validar_tamanho_imagem(arquivo)
    return arquivo


class SolicitacaoConsuladoForm(WhatsappObrigatorioMixin, forms.ModelForm):
    """Pedido de cadastro de consulado feito por um torcedor (o admin aceita ou recusa)."""

    foto = forms.ImageField(
        label="Foto do local (opcional)",
        required=False,
        help_text=f"Fachada ou interior do bar/sede. JPG, PNG ou WebP de até {TAMANHO_MAXIMO_IMAGEM_MB} MB.",
        widget=forms.FileInput(attrs={"accept": "image/jpeg,image/png,image/webp"}),
    )
    aceite_requisitos = forms.BooleanField(
        label="Declaro que o consulado atende a todos os requisitos do Santa Cruz listados acima.",
        error_messages={"required": "É preciso atender aos requisitos do clube para solicitar o cadastro."},
    )

    class Meta:
        model = Consulado
        fields = ("nome", "endereco", "latitude", "longitude", "link_whatsapp", "descricao")
        labels = {
            "nome": "Nome do consulado",
            "endereco": "Endereço do bar/sede",
            "link_whatsapp": "Link do grupo do WhatsApp",
            "descricao": "Conte sobre o consulado",
        }
        widgets = {
            "nome": forms.TextInput(attrs={"placeholder": "Ex.: Consulado Coral Caruaru"}),
            "endereco": forms.TextInput(attrs={"placeholder": "Rua, número, bairro, cidade - UF"}),
            # Preenchidos ao clicar no mapa do formulário.
            "latitude": forms.HiddenInput(),
            "longitude": forms.HiddenInput(),
            "link_whatsapp": forms.URLInput(attrs={"placeholder": "https://chat.whatsapp.com/..."}),
            "descricao": forms.Textarea(attrs={
                "rows": 4, "placeholder": "Dias e horários de encontro, telão, quantos torcedores costumam ir…",
            }),
        }
        error_messages = {
            "latitude": {"required": "Marque a localização do consulado no mapa."},
            "longitude": {"required": "Marque a localização do consulado no mapa."},
            "nome": {"unique": "Já existe um consulado com este nome."},
        }

    def clean_foto(self):
        return _validar_upload_imagem(self.cleaned_data.get("foto"))


class FotoConsuladoForm(forms.Form):
    """Nova foto da galeria do consulado."""

    imagem = forms.ImageField(
        label="Nova foto",
        help_text=f"Fachada, interior, telão, torcida… JPG, PNG ou WebP de até {TAMANHO_MAXIMO_IMAGEM_MB} MB.",
        error_messages={"required": "Escolha a foto que vai enviar."},
        widget=forms.FileInput(attrs={"accept": "image/jpeg,image/png,image/webp"}),
    )
    legenda = forms.CharField(
        label="Legenda (opcional)", max_length=150, required=False,
        widget=forms.TextInput(attrs={"placeholder": "Ex.: Telão no dia de jogo"}),
    )

    def clean_imagem(self):
        return _validar_upload_imagem(self.cleaned_data.get("imagem"))


class LegendaFotoForm(forms.Form):
    legenda = forms.CharField(label="Legenda", max_length=150, required=False)


class ReporteForm(forms.Form):
    """Problema ou sugestão enviada por qualquer usuário (só a administração vê)."""

    tipo = forms.ChoiceField(
        label="O que você quer enviar?", choices=Reporte.Tipo.choices, initial=Reporte.Tipo.PROBLEMA,
        widget=forms.RadioSelect,
    )
    mensagem = forms.CharField(
        label="Conte para a gente",
        max_length=3000,
        widget=forms.Textarea(attrs={
            "rows": 6,
            "placeholder": "O que aconteceu, em qual tela e o que você esperava que acontecesse. Para sugestões, descreva a ideia.",
        }),
    )
    captura = forms.ImageField(
        label="Captura de tela (opcional)",
        required=False,
        help_text=f"Ajuda a entender o problema. JPG, PNG ou WebP de até {TAMANHO_MAXIMO_IMAGEM_MB} MB.",
        widget=forms.FileInput(attrs={"accept": "image/jpeg,image/png,image/webp"}),
    )
    pagina = forms.CharField(required=False, max_length=300, widget=forms.HiddenInput())

    def clean_captura(self):
        return _validar_upload_imagem(self.cleaned_data.get("captura"))


class RejeicaoForm(forms.Form):
    motivo = forms.CharField(
        label="Motivo (opcional, o solicitante verá)",
        required=False,
        widget=forms.Textarea(attrs={"rows": 2, "placeholder": "Ex.: endereço não confere, falta o grupo de WhatsApp…"}),
    )


# Cargos oferecidos na lista; "Outro cargo…" libera um campo para digitar qualquer outro.
CARGOS = (
    "Vice-presidente", "Secretário(a)", "Tesoureiro(a)", "Diretor(a) de eventos",
    "Diretor(a) de comunicação", "Diretor(a) social", "Conselheiro(a)",
)
OUTRO_CARGO = "__outro__"
OPCOES_CARGO = (("", "Sem cargo"), *((c, c) for c in CARGOS), (OUTRO_CARGO, "Outro cargo…"))


class CargoForm(forms.Form):
    """Cargo escolhido na lista ou digitado em "Outro cargo…"."""

    cargo = forms.CharField(label="Cargo", required=False, widget=forms.Select(choices=OPCOES_CARGO))
    cargo_outro = forms.CharField(
        label="Qual cargo?", max_length=60, required=False,
        widget=forms.TextInput(attrs={"placeholder": "Digite o cargo"}),
    )

    def clean(self):
        dados = super().clean()
        cargo = (dados.get("cargo") or "").strip()
        if cargo == OUTRO_CARGO:
            cargo = (dados.get("cargo_outro") or "").strip()
            if not cargo:
                self.add_error("cargo_outro", "Digite o nome do cargo.")
        if len(cargo) > 60:
            self.add_error("cargo", "O cargo pode ter no máximo 60 caracteres.")
        dados["cargo"] = cargo
        return dados


class NovoMembroForm(CargoForm):
    email = forms.EmailField(label="E-mail", widget=forms.EmailInput(attrs={"placeholder": "torcedor@email.com"}))
    nome = forms.CharField(
        label="Nome", max_length=150, required=False,
        help_text="Obrigatório só se a pessoa ainda não tiver conta no Conexão Coral.",
    )

    field_order = ("email", "nome", "cargo", "cargo_outro")

    def dados_membro(self) -> dict:
        return {campo: self.cleaned_data[campo] for campo in ("email", "nome", "cargo")}


class VariasImagensInput(forms.ClearableFileInput):
    """Campo de arquivo que aceita selecionar várias imagens de uma vez."""

    allow_multiple_selected = True


class VariasImagensField(forms.ImageField):
    """Lista de imagens enviadas (cada uma validada como imagem, formato e tamanho)."""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("widget", VariasImagensInput(attrs={"accept": "image/jpeg,image/png,image/webp"}))
        kwargs.setdefault("required", False)
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        arquivos = data if isinstance(data, (list, tuple)) else ([data] if data else [])
        return [_validar_upload_imagem(super(VariasImagensField, self).clean(a, initial)) for a in arquivos]


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
    limite_vagas = forms.IntegerField(
        label="Limite de vagas (opcional)",
        required=False,
        min_value=1,
        help_text="Para eventos com número de pessoas restrito. Deixe em branco para não limitar.",
        widget=forms.NumberInput(attrs={"placeholder": "Sem limite", "inputmode": "numeric"}),
        error_messages={"min_value": "O limite precisa ser de pelo menos 1 vaga."},
    )
    fotos = VariasImagensField(
        label="Fotos do evento (opcional)",
        help_text=f"Cartaz, local, edições anteriores… Selecione uma ou várias de uma vez. "
                  f"JPG, PNG ou WebP de até {TAMANHO_MAXIMO_IMAGEM_MB} MB cada.",
    )
    # Na edição: fotos já salvas marcadas para sair (as opções são as fotos do evento).
    remover_fotos = forms.TypedMultipleChoiceField(coerce=int, required=False, widget=forms.CheckboxSelectMultiple)

    @classmethod
    def para_evento(cls, evento, dados=None, arquivos=None) -> "EventoForm":
        """Formulário de edição já preenchido com os dados do evento."""
        horas = round((evento.data_hora_fim - evento.data_hora_inicio).total_seconds() / 3600)
        form = cls(dados, arquivos, initial={
            "titulo": evento.titulo,
            "descricao": evento.descricao,
            "inicio": timezone.localtime(evento.data_hora_inicio),
            "duracao": horas,
            "exclusivo_membros": evento.exclusivo_membros,
            "limite_vagas": evento.limite_vagas,
        })
        form.fotos_atuais = list(evento.fotos.all())
        form.fields["remover_fotos"].choices = [(foto.pk, foto.pk) for foto in form.fotos_atuais]
        # Duração fora das opções padrão (ex.: definida pela API) continua selecionável.
        if horas > 0 and horas not in dict(cls.DURACOES):
            form.fields["duracao"].choices = sorted([*cls.DURACOES, (horas, f"{horas} horas")])
        return form

    def dados_evento(self) -> dict:
        """Converte o formulário nos campos esperados por ``EventoService.criar_evento``."""
        inicio = self.cleaned_data["inicio"]
        dados = {
            "titulo": self.cleaned_data["titulo"].strip(),
            "descricao": self.cleaned_data["descricao"].strip(),
            "data_hora_inicio": inicio,
            "data_hora_fim": inicio + timedelta(hours=self.cleaned_data["duracao"]),
            "exclusivo_membros": self.cleaned_data["exclusivo_membros"],
            "limite_vagas": self.cleaned_data.get("limite_vagas"),
        }
        return dados
