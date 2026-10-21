"""Testes das páginas da interface web (login por sessão + mesmas regras da API)."""
from __future__ import annotations

from datetime import timedelta

from django.contrib.messages import get_messages
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from core.models import Aliado, CategoriaAliado, CheckIn, Evento, MembroConsulado, PresencaEvento, StatusAprovacao, TipoUsuario
from core.tests.factories import criar_consulado, criar_evento, criar_partida, criar_usuario


def mensagens(resposta) -> list[str]:
    return [str(m) for m in get_messages(resposta.wsgi_request)]


class AutenticacaoTests(TestCase):
    def test_paginas_exigem_login(self):
        for nome in ("web:consulados", "web:partidas", "web:aliados", "web:painel"):
            resposta = self.client.get(reverse(nome))
            self.assertRedirects(resposta, f"{reverse('web:login')}?next={reverse(nome)}", fetch_redirect_response=False)

    def test_login_por_email_sem_diferenciar_maiusculas(self):
        criar_usuario(email="torcedor@coral.com")
        resposta = self.client.post(
            reverse("web:login"), {"username": "Torcedor@Coral.com", "password": "SenhaForte#123"},
        )
        self.assertRedirects(resposta, reverse("web:consulados"), fetch_redirect_response=False)

    def test_login_invalido_mostra_erro(self):
        criar_usuario(email="torcedor@coral.com")
        resposta = self.client.post(reverse("web:login"), {"username": "torcedor@coral.com", "password": "errada"})
        self.assertContains(resposta, "E-mail ou senha incorretos.")

    def test_logout(self):
        self.client.force_login(criar_usuario())
        resposta = self.client.post(reverse("web:logout"))
        self.assertRedirects(resposta, reverse("web:login"), fetch_redirect_response=False)
        self.assertEqual(self.client.get(reverse("web:consulados")).status_code, 302)


class PaginasTests(TestCase):
    def setUp(self):
        self.torcedor = criar_usuario()
        self.consulado = criar_consulado(nome="Consulado Coral Olinda")
        self.client.force_login(self.torcedor)

    def test_mapa_lista_apenas_consulados_visiveis(self):
        criar_consulado(nome="Consulado Pendente", status_aprovacao=StatusAprovacao.PENDENTE)
        resposta = self.client.get(reverse("web:consulados"))
        self.assertContains(resposta, "Consulado Coral Olinda")
        self.assertNotContains(resposta, "Consulado Pendente")

    def test_detalhe_mostra_proximo_jogo_e_eventos(self):
        criar_partida(adversario="Sport")
        criar_evento(self.consulado, titulo="Resenha pré-jogo")
        resposta = self.client.get(reverse("web:consulado", args=[self.consulado.pk]))
        self.assertContains(resposta, "Santa Cruz x Sport")
        self.assertContains(resposta, "Resenha pré-jogo")
        self.assertContains(resposta, "Fazer check-in")

    def test_partidas_proximas_e_anteriores(self):
        criar_partida(adversario="Náutico", data_hora=timezone.now() + timedelta(days=3))
        criar_partida(adversario="Sport", data_hora=timezone.now() - timedelta(days=3))
        proximas = self.client.get(reverse("web:partidas"))
        self.assertContains(proximas, "Náutico")
        self.assertNotContains(proximas, "Sport")
        anteriores = self.client.get(reverse("web:partidas"), {"periodo": "anteriores"})
        self.assertContains(anteriores, "Sport")
        self.assertNotContains(anteriores, "Náutico")

    def test_aliados_filtra_por_categoria_e_busca(self):
        dono = criar_usuario(TipoUsuario.RESPONSAVEL_ALIADO)
        aprovado = {"usuario": dono, "status_aprovacao": StatusAprovacao.APROVADO}
        Aliado.objects.create(nome_negocio="Bar do Tricolor", categoria=CategoriaAliado.BAR, **aprovado)
        Aliado.objects.create(nome_negocio="Camisas Coral", categoria=CategoriaAliado.VESTUARIO, **aprovado)
        bares = self.client.get(reverse("web:aliados"), {"categoria": "BAR"})
        self.assertContains(bares, "Bar do Tricolor")
        self.assertNotContains(bares, "Camisas Coral")
        busca = self.client.get(reverse("web:aliados"), {"q": "camisas"})
        self.assertContains(busca, "Camisas Coral")
        self.assertNotContains(busca, "Bar do Tricolor")


class CheckInTests(TestCase):
    def setUp(self):
        self.torcedor = criar_usuario()
        self.consulado = criar_consulado()
        self.partida = criar_partida()
        self.client.force_login(self.torcedor)
        self.url = reverse("web:fazer-checkin", args=[self.consulado.pk])

    def test_checkin_filia_o_torcedor(self):
        resposta = self.client.post(self.url, {"partida": self.partida.pk})
        self.assertRedirects(resposta, reverse("web:consulado", args=[self.consulado.pk]), fetch_redirect_response=False)
        self.assertTrue(CheckIn.objects.filter(usuario=self.torcedor, partida=self.partida, ativo=True).exists())
        self.assertTrue(MembroConsulado.objects.filter(usuario=self.torcedor, consulado=self.consulado).exists())
        self.assertIn(f"Check-in confirmado! Agora você é membro do {self.consulado.nome}.", mensagens(resposta))

    def test_segundo_checkin_na_mesma_partida_e_recusado(self):
        self.client.post(self.url, {"partida": self.partida.pk})
        outro = criar_consulado()
        resposta = self.client.post(reverse("web:fazer-checkin", args=[outro.pk]), {"partida": self.partida.pk})
        self.assertIn("Você já possui um check-in ativo para esta partida.", mensagens(resposta))
        self.assertEqual(CheckIn.objects.filter(usuario=self.torcedor, ativo=True).count(), 1)

    def test_checkin_exige_post(self):
        self.assertEqual(self.client.get(self.url).status_code, 405)

    def test_cancelar_checkin(self):
        self.client.post(self.url, {"partida": self.partida.pk})
        checkin = CheckIn.objects.get(usuario=self.torcedor)
        resposta = self.client.post(reverse("web:cancelar-checkin", args=[checkin.pk]))
        checkin.refresh_from_db()
        self.assertFalse(checkin.ativo)
        self.assertIn("Check-in cancelado.", mensagens(resposta))

    def test_nao_cancela_checkin_de_outro_usuario(self):
        checkin = CheckIn.objects.create(usuario=criar_usuario(), partida=self.partida, consulado=self.consulado)
        resposta = self.client.post(reverse("web:cancelar-checkin", args=[checkin.pk]))
        self.assertEqual(resposta.status_code, 404)


class PresencaTests(TestCase):
    def setUp(self):
        self.torcedor = criar_usuario()
        self.consulado = criar_consulado()
        self.evento = criar_evento(self.consulado)
        self.client.force_login(self.torcedor)
        self.url = reverse("web:confirmar-presenca", args=[self.evento.pk])

    def test_nao_membro_nao_confirma(self):
        resposta = self.client.post(self.url)
        self.assertFalse(PresencaEvento.objects.exists())
        self.assertTrue(any("Apenas membros" in m for m in mensagens(resposta)))

    def test_membro_confirma(self):
        MembroConsulado.objects.create(usuario=self.torcedor, consulado=self.consulado)
        resposta = self.client.post(self.url)
        self.assertTrue(PresencaEvento.objects.filter(usuario=self.torcedor, evento=self.evento).exists())
        self.assertIn(f'Presença confirmada em "{self.evento.titulo}".', mensagens(resposta))


class PainelTests(TestCase):
    def setUp(self):
        self.embaixador = criar_usuario(TipoUsuario.RESPONSAVEL_CONSULADO)
        self.consulado = criar_consulado(responsavel=self.embaixador, nome="Consulado CoralJampa")
        self.client.force_login(self.embaixador)

    def test_torcedor_nao_acessa_painel(self):
        self.client.force_login(criar_usuario())
        self.assertEqual(self.client.get(reverse("web:painel")).status_code, 403)

    def test_painel_mostra_indicadores(self):
        partida = criar_partida()
        CheckIn.objects.create(usuario=criar_usuario(nome="Maria Coral"), partida=partida, consulado=self.consulado)
        resposta = self.client.get(reverse("web:painel"))
        self.assertContains(resposta, "Consulado CoralJampa")
        self.assertContains(resposta, "Maria Coral")
        self.assertEqual(resposta.context["publico_previsto"], 1)

    def test_editar_dados_do_consulado(self):
        resposta = self.client.post(reverse("web:editar-consulado", args=[self.consulado.pk]), {
            "endereco": "Av. Epitácio Pessoa, 1000",
            "link_whatsapp": "https://chat.whatsapp.com/abc",
            "descricao": "Telão em todos os jogos.",
        })
        self.assertEqual(resposta.status_code, 302)
        self.consulado.refresh_from_db()
        self.assertEqual(self.consulado.endereco, "Av. Epitácio Pessoa, 1000")

    def test_link_de_whatsapp_invalido_e_recusado(self):
        resposta = self.client.post(reverse("web:editar-consulado", args=[self.consulado.pk]), {
            "endereco": "Rua Tal", "link_whatsapp": "https://example.com/grupo", "descricao": "",
        })
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Informe um link válido do WhatsApp")

    def test_nao_edita_consulado_de_outro_responsavel(self):
        outro = criar_consulado()
        self.assertEqual(self.client.get(reverse("web:editar-consulado", args=[outro.pk])).status_code, 403)

    def test_novo_evento_nasce_pendente(self):
        inicio = timezone.localtime() + timedelta(days=2)
        resposta = self.client.post(reverse("web:novo-evento", args=[self.consulado.pk]), {
            "titulo": "Resenha pré-jogo",
            "descricao": "",
            "inicio": inicio.strftime("%Y-%m-%dT%H:%M"),
            "duracao": "3",
        })
        self.assertEqual(resposta.status_code, 302)
        evento = Evento.objects.get(titulo="Resenha pré-jogo")
        self.assertEqual(evento.status_aprovacao, StatusAprovacao.PENDENTE)
        self.assertEqual(evento.data_hora_fim - evento.data_hora_inicio, timedelta(hours=3))

    def test_evento_no_passado_e_recusado(self):
        inicio = timezone.localtime() - timedelta(days=1)
        resposta = self.client.post(reverse("web:novo-evento", args=[self.consulado.pk]), {
            "titulo": "Atrasado", "inicio": inicio.strftime("%Y-%m-%dT%H:%M"), "duracao": "3",
        })
        self.assertContains(resposta, "O evento não pode começar no passado.")
        self.assertFalse(Evento.objects.exists())
