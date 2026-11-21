"""
Aniversariante do dia.

* O nome de quem faz aniversário aparece na página do consulado, o dia inteiro,
  só para os membros (e para o embaixador e o admin). Aparece só o nome:
  nunca a idade nem a data de nascimento. Quem desmarca "Mostrar meu
  aniversário" no perfil não aparece.
* O embaixador, os membros com cargo e o admin têm o botão "Dar os parabéns no
  grupo": o WhatsApp abre com a mensagem pronta (o WhatsApp não oferece um meio
  oficial para um sistema postar sozinho em grupos comuns).
* Todo dia, o comando ``enviar_parabens`` (agendado no cron) manda o e-mail
  especial para cada aniversariante, uma única vez por ano.
* Quem nasceu em 29/02 comemora em 28/02 nos anos que não são bissextos.
"""
from __future__ import annotations

import calendar
import logging
from datetime import date
from urllib.parse import quote

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.db.models import Q, QuerySet
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone

from core.models import Consulado, Usuario
from core.services.consulado_service import ConsuladoService

logger = logging.getLogger(__name__)

# Ordem das bolinhas com as iniciais: preto, branco, vermelho (o preto nunca encosta no vermelho).
CORES_DAS_INICIAIS = ("preto", "branco", "vermelho")


def hoje() -> date:
    return timezone.localdate()


def _filtro_do_dia(dia: date) -> Q:
    filtro = Q(data_nascimento__month=dia.month, data_nascimento__day=dia.day)
    if dia.month == 2 and dia.day == 28 and not calendar.isleap(dia.year):
        filtro |= Q(data_nascimento__month=2, data_nascimento__day=29)
    return filtro


def faz_aniversario(nascimento: date | None, dia: date | None = None) -> bool:
    if nascimento is None:
        return False
    dia = dia or hoje()
    if (nascimento.month, nascimento.day) == (dia.month, dia.day):
        return True
    return (nascimento.month, nascimento.day) == (2, 29) and (dia.month, dia.day) == (2, 28) and not calendar.isleap(dia.year)


def iniciais(nome: str) -> str:
    partes = [p for p in (nome or "").split() if p[:1].isalpha()]
    if not partes:
        return "?"
    return (partes[0][0] + (partes[-1][0] if len(partes) > 1 else "")).upper()


def _juntar(nomes: list[str]) -> str:
    return nomes[0] if len(nomes) == 1 else f"{', '.join(nomes[:-1])} e {nomes[-1]}"


class AniversarioService:
    # ------------------------------------------------------------- consulado
    @staticmethod
    def aniversariantes_do_consulado(consulado: Consulado, dia: date | None = None) -> QuerySet[Usuario]:
        """Membros (e o embaixador) que fazem aniversário no dia e aceitam aparecer."""
        return (
            Usuario.objects.filter(_filtro_do_dia(dia or hoje()), is_active=True, mostrar_aniversario=True)
            .filter(Q(filiacoes__consulado=consulado) | Q(pk=consulado.responsavel_id))
            .distinct()
            .order_by("nome")
        )

    @staticmethod
    def pode_ver(usuario: Usuario, consulado: Consulado) -> bool:
        return ConsuladoService().pode_ver_whatsapp(usuario, consulado)

    @staticmethod
    def pode_parabenizar_no_grupo(usuario: Usuario, consulado: Consulado) -> bool:
        """Embaixador, membro com cargo ou admin."""
        return usuario.is_admin or ConsuladoService().pode_editar_fotos(usuario, consulado)

    @staticmethod
    def mensagem_do_grupo(consulado: Consulado, nomes: list[str]) -> str:
        destaque = _juntar([f"*{n}*" for n in nomes])
        parabens = (
            f"Parabéns para {destaque}, tricolor de coração! 🎂⚫⚪🔴" if len(nomes) == 1
            else f"Parabéns aos nossos tricolores {destaque}! 🎂⚫⚪🔴"
        )
        return (
            "🎉 *Hoje é dia de festa na Nação Coral!* 🎉\n\n"
            f"{parabens}\n\n"
            "Que o ano seja de muita saúde, alegria e vitórias do Mais Querido. Deixe seu parabéns aqui! 👇\n\n"
            f"_Conexão Coral · {consulado.nome}_"
        )

    @classmethod
    def link_whatsapp(cls, consulado: Consulado, nomes: list[str]) -> str:
        """Abre o WhatsApp com o texto pronto; quem toca escolhe o grupo e envia."""
        return "https://wa.me/?text=" + quote(cls.mensagem_do_grupo(consulado, nomes))

    def contexto_do_consulado(self, usuario: Usuario, consulado: Consulado) -> dict:
        """Dados do cartão "Aniversariantes de hoje" para a página do consulado."""
        if not self.pode_ver(usuario, consulado):
            return {}
        dia = hoje()
        lista = list(self.aniversariantes_do_consulado(consulado, dia))
        pessoas = [
            {"nome": u.nome, "iniciais": iniciais(u.nome), "cor": CORES_DAS_INICIAIS[i % 3], "eu": u.id == usuario.id}
            for i, u in enumerate(lista)
        ]
        contexto = {
            "aniversariantes": pessoas,
            # O cartão aparece quando há alguém além da própria pessoa (ela já vê a faixa de parabéns).
            "outros_aniversariantes": any(not p["eu"] for p in pessoas),
            # A faixa de "Feliz aniversário" aparece para a própria pessoa, mesmo que ela esconda o aniversário dos outros.
            "meu_aniversario": faz_aniversario(usuario.data_nascimento, dia),
            "parabens_por_email": usuario.aniversario_email_enviado_em == dia,
        }
        if pessoas and self.pode_parabenizar_no_grupo(usuario, consulado):
            contexto["link_parabens_grupo"] = self.link_whatsapp(consulado, [p["nome"] for p in pessoas])
        return contexto

    # ---------------------------------------------------------------- e-mail
    @staticmethod
    def aniversariantes_do_dia(dia: date | None = None) -> QuerySet[Usuario]:
        return Usuario.objects.filter(_filtro_do_dia(dia or hoje()), is_active=True).exclude(email="").order_by("nome")

    @staticmethod
    def _consulados_de(usuario: Usuario) -> list[Consulado]:
        return list(
            Consulado.objects.filter(Q(filiacoes__usuario=usuario) | Q(responsavel=usuario))
            .distinct().order_by("nome")
        )

    def montar_email(self, usuario: Usuario) -> EmailMultiAlternatives:
        consulados = self._consulados_de(usuario)
        site = settings.SITE_URL.rstrip("/")
        caminho = reverse("web:consulado", args=[consulados[0].pk]) if consulados else reverse("web:consulados")
        contexto = {
            "primeiro_nome": usuario.get_short_name(),
            "consulados": _juntar([c.nome for c in consulados]) if consulados else "",
            "varios_consulados": len(consulados) > 1,
            "link": site + caminho,
            "texto_botao": "Ver meu consulado" if consulados else "Abrir a Conexão Coral",
        }
        assunto = f"🎂 Feliz aniversário, {contexto['primeiro_nome']}! A Nação Coral celebra com você"
        email = EmailMultiAlternatives(
            subject=assunto,
            body=render_to_string("core/emails/aniversario.txt", contexto),
            to=[usuario.email],
        )
        email.attach_alternative(render_to_string("core/emails/aniversario.html", contexto), "text/html")
        return email

    def enviar_emails(self, dia: date | None = None) -> int:
        """Envia o e-mail de parabéns a quem faz aniversário e ainda não recebeu neste dia."""
        dia = dia or hoje()
        enviados = 0
        for usuario in self.aniversariantes_do_dia(dia).exclude(aniversario_email_enviado_em=dia):
            try:
                self.montar_email(usuario).send()
            except Exception:  # um e-mail com problema não impede os outros
                logger.exception("Falha ao enviar o e-mail de aniversário para o usuário #%s", usuario.pk)
                continue
            Usuario.objects.filter(pk=usuario.pk).update(aniversario_email_enviado_em=dia)
            enviados += 1
        return enviados
