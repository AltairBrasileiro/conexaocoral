"""Aniversariante do dia: destaque no consulado, parabéns no grupo e e-mail automático."""
from __future__ import annotations

from datetime import date
from io import StringIO
from unittest import mock
from urllib.parse import unquote

from django.core import mail
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse

from core.models import MembroConsulado, Usuario
from core.services import AniversarioService
from core.services.aniversario_service import faz_aniversario, iniciais
from core.tests.factories import criar_consulado, criar_usuario

HOJE = date(2026, 11, 21)


def nascido_hoje(ano: int = 1990) -> date:
    return HOJE.replace(year=ano)


@mock.patch("core.services.aniversario_service.hoje", return_value=HOJE)
class AniversarioNoConsuladoTests(TestCase):
    def setUp(self):
        self.embaixador = criar_usuario(nome="Altair Juba")
        self.consulado = criar_consulado(responsavel=self.embaixador, nome="Consulado CoralJampa")
        MembroConsulado.objects.create(usuario=self.embaixador, consulado=self.consulado)
        self.nathalia = self._membro("Nathalia Francine", nascido_hoje(1995))
        self.maju = self._membro("Maju Guerra", nascido_hoje(1998))
        self.rubens = self._membro("Rubens Sousa", nascido_hoje(1987))
        self.outro = self._membro("Zé Ninguém", date(1990, 1, 5))
        self.url = reverse("web:consulado", args=[self.consulado.pk])

    def _membro(self, nome, nascimento, **extra):
        usuario = criar_usuario(nome=nome, data_nascimento=nascimento, **extra)
        MembroConsulado.objects.create(usuario=usuario, consulado=self.consulado)
        return usuario

    def test_membro_ve_os_aniversariantes_nas_cores_preto_branco_vermelho(self, _):
        self.client.force_login(self._membro("Leitor Comum", None))
        resposta = self.client.get(self.url)
        self.assertContains(resposta, "Aniversariantes de hoje")
        html = resposta.content.decode()
        posicoes = [html.index(n) for n in ("Maju Guerra", "Nathalia Francine", "Rubens Sousa")]
        self.assertEqual(posicoes, sorted(posicoes))  # ordem alfabética
        self.assertIn('iniciais--preto" aria-hidden="true">MG<', html)
        self.assertIn('iniciais--branco" aria-hidden="true">NF<', html)
        self.assertIn('iniciais--vermelho" aria-hidden="true">RS<', html)
        self.assertNotContains(resposta, "Zé Ninguém</strong>")
        # Nunca mostra a idade nem a data de nascimento.
        self.assertNotContains(resposta, "1995")
        # Membro comum não tem o botão do grupo.
        self.assertNotContains(resposta, "Dar os parabéns no grupo")

    def test_embaixador_tem_o_botao_com_a_mensagem_pronta(self, _):
        self.client.force_login(self.embaixador)
        resposta = self.client.get(self.url)
        link = resposta.context["link_parabens_grupo"]
        self.assertTrue(link.startswith("https://wa.me/?text="))
        texto = unquote(link.split("=", 1)[1])
        self.assertIn("*Maju Guerra*, *Nathalia Francine* e *Rubens Sousa*", texto)
        self.assertIn("Consulado CoralJampa", texto)

    def test_membro_com_cargo_tambem_parabeniza_no_grupo(self, _):
        MembroConsulado.objects.filter(usuario=self.outro).update(cargo="Tesoureiro")
        self.client.force_login(self.outro)
        self.assertContains(self.client.get(self.url), "Dar os parabéns no grupo")

    def test_quem_nao_e_membro_nao_ve(self, _):
        self.client.force_login(criar_usuario())
        self.assertNotContains(self.client.get(self.url), "Aniversariantes de hoje")

    def test_quem_esconde_o_aniversario_nao_aparece(self, _):
        Usuario.objects.filter(pk=self.maju.pk).update(mostrar_aniversario=False)
        self.client.force_login(self.outro)
        self.assertNotContains(self.client.get(self.url), "Maju Guerra")

    def test_aniversariante_ve_a_faixa_de_parabens(self, _):
        self.client.force_login(self.nathalia)
        resposta = self.client.get(self.url)
        self.assertContains(resposta, "Feliz aniversário, Nathalia!")
        self.assertContains(resposta, "É você!")

    def test_sem_aniversariantes_nao_mostra_nada(self, _):
        Usuario.objects.filter(pk__in=[self.nathalia.pk, self.maju.pk, self.rubens.pk]).update(data_nascimento=date(1990, 3, 3))
        self.client.force_login(self.outro)
        self.assertNotContains(self.client.get(self.url), "Aniversariantes de hoje")

    def test_perfil_permite_esconder_o_aniversario(self, _):
        self.client.force_login(self.maju)
        self.client.post(reverse("web:atualizar-perfil"), {
            "nome": "Maju Guerra", "email": self.maju.email, "data_nascimento": "1998-11-21",
            "telefone": "(83) 99999-1234", "cpf": "529.982.247-25",
        })
        self.maju.refresh_from_db()
        self.assertFalse(self.maju.mostrar_aniversario)


class RegrasDeDataTests(TestCase):
    def test_29_de_fevereiro_comemora_em_28_nos_anos_comuns(self):
        self.assertTrue(faz_aniversario(date(2000, 2, 29), date(2027, 2, 28)))
        self.assertFalse(faz_aniversario(date(2000, 2, 29), date(2028, 2, 28)))
        self.assertTrue(faz_aniversario(date(2000, 2, 29), date(2028, 2, 29)))

    def test_iniciais(self):
        self.assertEqual(iniciais("Nathalia Francine"), "NF")
        self.assertEqual(iniciais("Maju"), "M")
        self.assertEqual(iniciais("Rubens de Sousa"), "RS")


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend", SITE_URL="https://conexaocoral.com.br")
class EmailDeParabensTests(TestCase):
    def setUp(self):
        self.consulado = criar_consulado(nome="Consulado CoralJampa")
        self.nathalia = criar_usuario(nome="Nathalia Francine", data_nascimento=nascido_hoje(1995))
        MembroConsulado.objects.create(usuario=self.nathalia, consulado=self.consulado)
        criar_usuario(nome="Zé Ninguém", data_nascimento=date(1990, 1, 5))

    def test_envia_uma_vez_so_para_o_aniversariante(self):
        saida = StringIO()
        call_command("enviar_parabens", "--data", HOJE.isoformat(), stdout=saida)
        self.assertIn("1 e-mail", saida.getvalue())
        self.assertEqual(len(mail.outbox), 1)
        email = mail.outbox[0]
        self.assertEqual(email.to, [self.nathalia.email])
        self.assertIn("Feliz aniversário, Nathalia!", email.subject)
        self.assertIn("Consulado CoralJampa", email.body)
        html = email.alternatives[0][0]
        self.assertIn("Parabéns, tricolor!", html)
        self.assertIn(f"https://conexaocoral.com.br/consulados/{self.consulado.pk}/", html)
        # Rodar de novo no mesmo dia não repete.
        call_command("enviar_parabens", "--data", HOJE.isoformat(), stdout=StringIO())
        self.assertEqual(len(mail.outbox), 1)

    def test_email_vai_mesmo_para_quem_esconde_o_aniversario_no_consulado(self):
        Usuario.objects.filter(pk=self.nathalia.pk).update(mostrar_aniversario=False)
        self.assertEqual(AniversarioService().enviar_emails(HOJE), 1)

    def test_conta_desativada_nao_recebe(self):
        Usuario.objects.filter(pk=self.nathalia.pk).update(is_active=False)
        self.assertEqual(AniversarioService().enviar_emails(HOJE), 0)
