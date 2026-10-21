"""
Popula o banco com dados de demonstração (usuários, consulados, partidas,
eventos e aliados) para navegar pelo app sem cadastrar nada à mão.

    python manage.py popular_demo

Pode ser executado várias vezes: os registros são atualizados, não duplicados.
O próximo jogo tem data fixa (DATA_PROXIMO_JOGO); as demais partidas e o
evento pré-jogo são marcados em relação a ele.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from core.models import (
    Aliado,
    CategoriaAliado,
    CheckIn,
    Consulado,
    Evento,
    FotoConsulado,
    MandoCampo,
    MembroConsulado,
    Partida,
    PresencaEvento,
    StatusAprovacao,
    TipoUsuario,
    Usuario,
)

SENHA_DEMO = "Coral@2026"
APROVADO = StatusAprovacao.APROVADO

USUARIOS = [
    # (e-mail, nome, papel)
    ("admin@coral.com", "Admin Coral", TipoUsuario.ADMIN),
    ("torcedor@coral.com", "Joana Tricolor", TipoUsuario.TORCEDOR),
    ("embaixador@coral.com", "Carlos Embaixador", TipoUsuario.RESPONSAVEL_CONSULADO),
    ("embaixadora.sp@coral.com", "Marta Paulista", TipoUsuario.RESPONSAVEL_CONSULADO),
    ("rubens.sousa@coral.com", "Rubens Sousa", TipoUsuario.RESPONSAVEL_CONSULADO),
    ("lojista@coral.com", "Rui do Comércio", TipoUsuario.RESPONSAVEL_ALIADO),
]

CONSULADOS = [
    # (nome, responsável, endereço, lat, lng, descrição)
    ("Consulado Coral Boa Viagem", "embaixador@coral.com",
     "Av. Boa Viagem, 3200 - Boa Viagem, Recife/PE", "-8.118500", "-34.894500",
     "Bar oficial da torcida na orla. Telão, chope gelado e resenha em todo jogo."),
    ("Consulado Coral Olinda", "embaixador@coral.com",
     "Rua do Amparo, 45 - Carmo, Olinda/PE", "-8.013000", "-34.855000",
     "Sede no Sítio Histórico, com batucada antes das partidas."),
    ("Consulado CoralJampa", "rubens.sousa@coral.com",
     "João Pessoa/PB", "-7.115000", "-34.823000",
     "O ponto de encontro da Nação Coral em João Pessoa - PB."),
    ("Consulado Coral São Paulo", "embaixadora.sp@coral.com",
     "Rua Augusta, 1500 - Consolação, São Paulo/SP", "-23.556000", "-46.662000",
     "A casa dos pernambucanos tricolores em São Paulo."),
    ("Consulado Coral Rio", "embaixadora.sp@coral.com",
     "Rua Barata Ribeiro, 300 - Copacabana, Rio de Janeiro/RJ", "-22.967000", "-43.184000",
     "Ponto de encontro da torcida coral no Rio."),
]

# Fotos livres do Wikimedia Commons (servidas com CORS liberado, então o app web consegue exibi-las).
_COMMONS = "https://upload.wikimedia.org/wikipedia/commons/thumb"
FOTOS = [
    (f"{_COMMONS}/a/a9/Arruda_-_Santa_Cruz_-_panoramio.jpg/960px-Arruda_-_Santa_Cruz_-_panoramio.jpg",
     "Arruda em dia de jogo"),
    (f"{_COMMONS}/6/6b/Santa_Cruz_1X0_Sport_-_Pernambucano_BetNacional_2025_-_54302315558.jpg/"
     "960px-Santa_Cruz_1X0_Sport_-_Pernambucano_BetNacional_2025_-_54302315558.jpg", "Clássico das Multidões"),
    (f"{_COMMONS}/5/58/Por_do_Sol_-_Arruda_-_Santa_Cruz_Campe%C3%A3o_PE_2011_-_panoramio.jpg/"
     "960px-Por_do_Sol_-_Arruda_-_Santa_Cruz_Campe%C3%A3o_PE_2011_-_panoramio.jpg", "Pôr do sol no Arruda"),
    (f"{_COMMONS}/8/8a/Arruda_Stadium.jpg/960px-Arruda_Stadium.jpg", "Estádio do Arruda"),
    (f"{_COMMONS}/c/c7/Santa_Cruz_1X0_Sport_-_Pernambucano_BetNacional_2025_-_54302316338.jpg/"
     "960px-Santa_Cruz_1X0_Sport_-_Pernambucano_BetNacional_2025_-_54302316338.jpg", "Torcida coral"),
]

# Próximo jogo com data oficial; as demais partidas são marcadas a partir dele.
DATA_PROXIMO_JOGO = datetime(2027, 5, 7, 17, 0, tzinfo=ZoneInfo("America/Sao_Paulo"))

# Logos exibidos no pino do mapa (servidos pela API em media/logos/).
LOGOS = {"Consulado CoralJampa": "logos/logocj.png"}

# Imagem exclusiva de um consulado: substitui, só na galeria dele, a foto indicada.
# Caminhos relativos são servidos pela própria API (media/).
FOTOS_EXCLUSIVAS = {
    "Consulado CoralJampa": {"Pôr do sol no Arruda": ("logos/logocj.png", "Torcida CoralJampa")},
}

# Registros de versões anteriores da demo que são renomeados (e não recriados),
# preservando membros, fotos e check-ins já vinculados a eles.
CONSULADOS_RENOMEADOS = {"Consulado Coral João Pessoa": "Consulado CoralJampa"}
PARTIDAS_RENOMEADAS = {
    ("Sport", "Campeonato Pernambucano"): ("Floresta", "Série C"),
    ("Floresta", "Série C"): ("Corinthians", "Copa do Brasil"),
    ("Corinthians", "Copa do Brasil"): ("Corinthians", "Brasileiro Série B"),
}

ALIADOS = [
    # (nome, categoria, descrição, instagram, verificado)
    ("Bar do Arruda", CategoriaAliado.BAR, "Petiscos e cerveja a 200 m do estádio.",
     "https://instagram.com/bardoarruda", True),
    ("Camisas Coral Store", CategoriaAliado.VESTUARIO, "Camisas, bonés e agasalhos da torcida.",
     "https://instagram.com/camisascoral", True),
    ("Cantinho Tricolor", CategoriaAliado.RESTAURANTE, "Comida regional com desconto para sócios.",
     "https://instagram.com/cantinhotricolor", False),
    ("Coral Transfers", CategoriaAliado.SERVICOS, "Vans para jogos fora de casa.",
     "https://instagram.com/coraltransfers", True),
    ("Tricolor Artigos", CategoriaAliado.LOJA, "Chaveiros, canecas e bandeiras.",
     "https://instagram.com/tricolorartigos", False),
]


class Command(BaseCommand):
    help = "Popula o banco com dados de demonstração do Conexão Coral."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--url-base", default="http://localhost:8000",
            help="Endereço público da API, usado nas URLs das imagens servidas por ela.",
        )
        parser.add_argument(
            "--forcar", action="store_true",
            help="Permite rodar com DEBUG=False (não recomendado: cria contas com senha conhecida).",
        )

    @transaction.atomic
    def handle(self, *args, **options) -> None:
        if not settings.DEBUG and not options["forcar"]:
            raise CommandError("Recusado com DEBUG=False: as contas de demo têm senha pública. Use --forcar.")

        agora = timezone.now()
        usuarios = {email: self._usuario(email, nome, papel) for email, nome, papel in USUARIOS}

        for antigo, novo in CONSULADOS_RENOMEADOS.items():
            if not Consulado.objects.filter(nome=novo).exists():
                Consulado.objects.filter(nome=antigo).update(nome=novo)
        for (adv_antigo, camp_antigo), (adv_novo, camp_novo) in PARTIDAS_RENOMEADAS.items():
            if not Partida.objects.filter(adversario=adv_novo, campeonato=camp_novo).exists():
                Partida.objects.filter(adversario=adv_antigo, campeonato=camp_antigo).update(
                    adversario=adv_novo, campeonato=camp_novo,
                )
        url_media = f"{options['url_base'].rstrip('/')}/{settings.MEDIA_URL.strip('/')}/"

        consulados = []
        for nome, email_resp, endereco, lat, lng, descricao in CONSULADOS:
            # Troca de responsável: o anterior deixa de ser membro (só era por ser o responsável).
            anterior = Consulado.objects.filter(nome=nome).exclude(responsavel=usuarios[email_resp]).first()
            if anterior is not None:
                MembroConsulado.objects.filter(consulado=anterior, usuario_id=anterior.responsavel_id).delete()
            consulado, _ = Consulado.objects.update_or_create(
                nome=nome,
                defaults={
                    "responsavel": usuarios[email_resp], "endereco": endereco,
                    "latitude": lat, "longitude": lng, "descricao": descricao,
                    "link_whatsapp": "https://chat.whatsapp.com/ConviteConsuladoCoral",
                    "status_aprovacao": APROVADO,
                    "logo_url": url_media + LOGOS[nome] if nome in LOGOS else "",
                },
            )
            MembroConsulado.objects.get_or_create(usuario=usuarios[email_resp], consulado=consulado)
            consulados.append(consulado)

        # Cada consulado recebe 3 fotos, em rodízio, para a galeria da tela de detalhes.
        for indice, consulado in enumerate(consulados):
            consulado.fotos.all().delete()
            for ordem in range(3):
                url, legenda = FOTOS[(indice + ordem) % len(FOTOS)]
                url, legenda = FOTOS_EXCLUSIVAS.get(consulado.nome, {}).get(legenda, (url, legenda))
                if not url.startswith("http"):
                    url = url_media + url
                FotoConsulado.objects.create(consulado=consulado, url=url, legenda=legenda, ordem=ordem)

        jogo = DATA_PROXIMO_JOGO
        partidas = [
            self._partida("Corinthians", MandoCampo.CASA, "Brasileiro Série B", jogo, "Globo"),
            self._partida("Náutico", MandoCampo.FORA, "Campeonato Pernambucano", jogo + timedelta(days=4), "Premiere"),
            self._partida("Treze", MandoCampo.CASA, "Copa do Nordeste", jogo + timedelta(days=9), "SBT"),
            self._partida("Botafogo-PB", MandoCampo.FORA, "Série C", jogo + timedelta(days=15), "DAZN"),
            self._partida("Ferroviário", MandoCampo.CASA, "Série C", jogo + timedelta(days=22), "DAZN"),
        ]

        boa_viagem = consulados[0]
        eventos = [
            self._evento(boa_viagem, "Resenha pré-jogo", "Concentração com batucada e chope.",
                         jogo - timedelta(hours=2), exclusivo=False),
            self._evento(boa_viagem, "Churrasco dos sócios", "Exclusivo para membros do consulado.",
                         self._dia(agora, 6, 18), exclusivo=True),
            self._evento(consulados[1], "Bloco Coral no Carmo", "Saída do bloco pelas ladeiras.",
                         self._dia(agora, 10, 16), exclusivo=False),
        ]

        # A torcedora demo já é membro de Boa Viagem, com check-in e presença,
        # para os contadores do painel do responsável não aparecerem zerados.
        torcedora = usuarios["torcedor@coral.com"]
        MembroConsulado.objects.get_or_create(usuario=torcedora, consulado=boa_viagem)
        CheckIn.objects.get_or_create(
            usuario=torcedora, partida=partidas[1], ativo=True, defaults={"consulado": boa_viagem},
        )
        PresencaEvento.objects.get_or_create(usuario=torcedora, evento=eventos[0])

        for nome, categoria, descricao, instagram, verificado in ALIADOS:
            Aliado.objects.update_or_create(
                nome_negocio=nome,
                defaults={
                    "usuario": usuarios["lojista@coral.com"], "categoria": categoria,
                    "descricao": descricao, "link_instagram": instagram,
                    "link_whatsapp": "https://wa.me/5581999999999",
                    "status_aprovacao": APROVADO, "selo_verificado": verificado,
                },
            )

        self.stdout.write(self.style.SUCCESS(
            f"Demo pronta: {len(usuarios)} usuários, {len(consulados)} consulados, "
            f"{len(partidas)} partidas, {len(eventos)} eventos, {len(ALIADOS)} aliados."
        ))
        self.stdout.write(f"Senha de todas as contas: {SENHA_DEMO}")
        for email, _, papel in USUARIOS:
            self.stdout.write(f"  {email:<28} {papel}")

    def _usuario(self, email: str, nome: str, papel: str) -> Usuario:
        usuario = Usuario.objects.filter(email=email).first()
        if usuario is None:
            criar = Usuario.objects.create_superuser if papel == TipoUsuario.ADMIN else Usuario.objects.create_user
            return criar(email=email, password=SENHA_DEMO, nome=nome, tipo_usuario=papel)
        usuario.nome, usuario.tipo_usuario, usuario.is_active = nome, papel, True
        usuario.set_password(SENHA_DEMO)
        usuario.save()
        return usuario

    @staticmethod
    def _dia(agora, dias: int, hora: int):
        """Daqui a ``dias`` dias, em hora cheia no fuso local (ex.: 18h)."""
        local = timezone.localtime(agora) + timedelta(days=dias)
        return local.replace(hour=hora, minute=0, second=0, microsecond=0)

    @staticmethod
    def _partida(adversario: str, mando: str, campeonato: str, data_hora, canal: str) -> Partida:
        partida, _ = Partida.objects.update_or_create(
            adversario=adversario, campeonato=campeonato,
            defaults={"mando_campo": mando, "data_hora": data_hora, "canal_transmissao": canal},
        )
        return partida

    @staticmethod
    def _evento(consulado: Consulado, titulo: str, descricao: str, inicio, exclusivo: bool) -> Evento:
        evento, _ = Evento.objects.update_or_create(
            consulado=consulado, titulo=titulo,
            defaults={
                "descricao": descricao, "data_hora_inicio": inicio,
                "data_hora_fim": inicio + timedelta(hours=4),
                "exclusivo_membros": exclusivo, "status_aprovacao": APROVADO,
            },
        )
        return evento
