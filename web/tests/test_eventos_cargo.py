"""Eventos do consulado gerenciados por membros com cargo (além do embaixador e do admin)."""
from __future__ import annotations

from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from core.models import Evento, MembroConsulado, StatusAprovacao, TipoUsuario
from core.tests.factories import criar_consulado, criar_evento, criar_usuario


class EventosDoMembroComCargoTests(TestCase):
    def setUp(self):
        self.embaixador = criar_usuario(TipoUsuario.RESPONSAVEL_CONSULADO)
        self.consulado = criar_consulado(responsavel=self.embaixador, nome="Consulado Coral Olinda")
        MembroConsulado.objects.create(usuario=self.embaixador, consulado=self.consulado)
        self.diretor = criar_usuario(nome="Dani Diretora")
        MembroConsulado.objects.create(usuario=self.diretor, consulado=self.consulado, cargo="Diretor(a) de eventos")
        self.membro_sem_cargo = criar_usuario()
        MembroConsulado.objects.create(usuario=self.membro_sem_cargo, consulado=self.consulado)
        self.url_novo = reverse("web:novo-evento", args=[self.consulado.pk])
        self.client.force_login(self.diretor)

    def _dados(self, titulo="Resenha da diretoria", **extra):
        inicio = timezone.localtime() + timedelta(days=2)
        return {"titulo": titulo, "descricao": "", "inicio": inicio.strftime("%Y-%m-%dT%H:%M"), "duracao": "3", **extra}

    def test_cria_evento_ja_publicado(self):
        resposta = self.client.post(self.url_novo, self._dados())
        self.assertEqual(resposta.status_code, 302)
        evento = Evento.objects.get(titulo="Resenha da diretoria")
        self.assertEqual(evento.consulado, self.consulado)
        self.assertEqual(evento.status_aprovacao, StatusAprovacao.APROVADO)

    def test_edita_e_exclui_evento(self):
        evento = criar_evento(self.consulado, titulo="Resenha")
        inicio = timezone.localtime(evento.data_hora_inicio)
        resposta = self.client.post(
            reverse("web:editar-evento", args=[evento.pk]),
            self._dados("Resenha pré-jogo", inicio=inicio.strftime("%Y-%m-%dT%H:%M")),
        )
        self.assertEqual(resposta.status_code, 302)
        evento.refresh_from_db()
        self.assertEqual(evento.titulo, "Resenha pré-jogo")
        self.client.post(reverse("web:excluir-evento", args=[evento.pk]))
        self.assertFalse(Evento.objects.filter(pk=evento.pk).exists())

    def test_painel_e_pagina_do_consulado_mostram_os_atalhos(self):
        evento = criar_evento(self.consulado, titulo="Resenha")
        painel = self.client.get(reverse("web:painel"))
        self.assertContains(painel, self.url_novo)
        self.assertContains(painel, reverse("web:editar-evento", args=[evento.pk]))
        # As configurações do consulado continuam só com o embaixador.
        self.assertNotContains(painel, reverse("web:editar-consulado", args=[self.consulado.pk]))
        self.assertNotContains(painel, reverse("web:membros", args=[self.consulado.pk]))
        pagina = self.client.get(reverse("web:consulado", args=[self.consulado.pk]))
        self.assertContains(pagina, reverse("web:editar-evento", args=[evento.pk]))

    def test_membro_sem_cargo_nao_gerencia(self):
        evento = criar_evento(self.consulado)
        self.client.force_login(self.membro_sem_cargo)
        self.assertEqual(self.client.get(self.url_novo).status_code, 403)
        self.assertEqual(self.client.post(self.url_novo, self._dados()).status_code, 403)
        self.assertEqual(self.client.get(reverse("web:editar-evento", args=[evento.pk])).status_code, 403)
        self.assertEqual(self.client.post(reverse("web:excluir-evento", args=[evento.pk])).status_code, 403)
        self.assertTrue(Evento.objects.filter(pk=evento.pk).exists())
        pagina = self.client.get(reverse("web:consulado", args=[self.consulado.pk]))
        self.assertNotContains(pagina, reverse("web:editar-evento", args=[evento.pk]))

    def test_cargo_em_outro_consulado_nao_vale(self):
        outro = criar_consulado()
        evento = criar_evento(outro)
        self.assertEqual(self.client.get(reverse("web:novo-evento", args=[outro.pk])).status_code, 403)
        self.assertEqual(self.client.get(reverse("web:editar-evento", args=[evento.pk])).status_code, 403)
        self.assertEqual(self.client.post(reverse("web:excluir-evento", args=[evento.pk])).status_code, 403)

    def test_perder_o_cargo_tira_o_acesso(self):
        MembroConsulado.objects.filter(usuario=self.diretor).update(cargo="")
        self.assertEqual(self.client.get(self.url_novo).status_code, 403)


class EventosDoMembroComCargoApiTests(TestCase):
    def setUp(self):
        self.consulado = criar_consulado()
        self.diretor = criar_usuario()
        MembroConsulado.objects.create(usuario=self.diretor, consulado=self.consulado, cargo="Diretor(a) de eventos")
        self.torcedor = criar_usuario()
        self.api = APIClient()
        self.api.force_authenticate(self.diretor)

    def _dados(self):
        inicio = timezone.now() + timedelta(days=2)
        return {
            "consulado": self.consulado.pk, "titulo": "Resenha da diretoria",
            "data_hora_inicio": inicio.isoformat(), "data_hora_fim": (inicio + timedelta(hours=3)).isoformat(),
        }

    def test_cria_edita_e_exclui_pela_api(self):
        resposta = self.api.post("/api/v1/eventos/", self._dados(), format="json")
        self.assertEqual(resposta.status_code, 201, resposta.data)
        url = f"/api/v1/eventos/{resposta.data['id']}/"
        self.assertEqual(self.api.patch(url, {"titulo": "Resenha pré-jogo"}, format="json").status_code, 200)
        self.assertEqual(self.api.delete(url).status_code, 204)
        self.assertFalse(Evento.objects.exists())

    def test_torcedor_sem_cargo_nao_gerencia_pela_api(self):
        evento = criar_evento(self.consulado)
        self.api.force_authenticate(self.torcedor)
        self.assertIn(self.api.post("/api/v1/eventos/", self._dados(), format="json").status_code, (400, 403))
        url = f"/api/v1/eventos/{evento.pk}/"
        self.assertEqual(self.api.patch(url, {"titulo": "Invadido"}, format="json").status_code, 403)
        self.assertEqual(self.api.delete(url).status_code, 403)
        self.assertFalse(Evento.objects.filter(titulo="Resenha da diretoria").exists())
        self.assertTrue(Evento.objects.filter(pk=evento.pk).exists())
