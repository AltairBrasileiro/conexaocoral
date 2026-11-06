"""Testes de integração das principais regras de negócio via API."""
from __future__ import annotations

from datetime import timedelta

from django.core.cache import cache
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from core.models import MembroConsulado, StatusAprovacao, TipoUsuario, TokenWhitelist
from core.tests.factories import criar_consulado, criar_evento, criar_usuario


class BaseAPITestCase(APITestCase):
    """Limpa o cache (contadores de throttle) e oferece login real via API."""

    def setUp(self):
        super().setUp()
        cache.clear()

    def autenticar(self, usuario, senha: str = "SenhaForte#123") -> dict:
        resposta = self.client.post("/api/v1/auth/login/", {"email": usuario.email, "password": senha})
        assert resposta.status_code == status.HTTP_200_OK, resposta.data
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {resposta.data['access']}")
        return resposta.data


class AuthWhitelistTests(BaseAPITestCase):
    def test_login_registra_tokens_e_logout_revoga(self):
        usuario = criar_usuario()
        tokens = self.autenticar(usuario)
        self.assertEqual(TokenWhitelist.objects.filter(usuario=usuario).count(), 2)

        self.assertEqual(self.client.get("/api/v1/usuarios/me/").status_code, status.HTTP_200_OK)

        resposta = self.client.post("/api/v1/auth/logout/", {"refresh": tokens["refresh"]})
        self.assertEqual(resposta.status_code, status.HTTP_204_NO_CONTENT)

        # Mesmo sem expirar, o access token deixa de valer.
        self.assertEqual(self.client.get("/api/v1/usuarios/me/").status_code, status.HTTP_401_UNAUTHORIZED)

    def test_refresh_rotaciona_e_invalida_refresh_antigo(self):
        tokens = self.autenticar(criar_usuario())
        self.client.credentials()
        primeira = self.client.post("/api/v1/auth/refresh/", {"refresh": tokens["refresh"]})
        self.assertEqual(primeira.status_code, status.HTTP_200_OK)
        # Reutilizar o refresh antigo deve falhar (saiu da whitelist).
        segunda = self.client.post("/api/v1/auth/refresh/", {"refresh": tokens["refresh"]})
        self.assertEqual(segunda.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_registro_nao_permite_papel_admin(self):
        resposta = self.client.post("/api/v1/auth/registro/", {
            "nome": "Hacker", "email": "h@x.com", "tipo_usuario": TipoUsuario.ADMIN,
            "password": "SenhaForte#123", "password_confirmacao": "SenhaForte#123",
        })
        self.assertEqual(resposta.status_code, status.HTTP_400_BAD_REQUEST)


class EntradaComoMembroTests(BaseAPITestCase):
    def setUp(self):
        super().setUp()
        self.torcedor = criar_usuario()
        self.consulado = criar_consulado()
        self.autenticar(self.torcedor)

    def test_entrada_como_membro_depende_do_embaixador(self):
        pedido = self.client.post(f"/api/v1/consulados/{self.consulado.id}/solicitar-entrada/")
        self.assertEqual(pedido.status_code, status.HTTP_201_CREATED, pedido.data)
        repetido = self.client.post(f"/api/v1/consulados/{self.consulado.id}/solicitar-entrada/")
        self.assertEqual(repetido.status_code, status.HTTP_409_CONFLICT)
        # O torcedor não responde o próprio pedido.
        proprio = self.client.post(f"/api/v1/consulados/{self.consulado.id}/responder-entrada/",
                                   {"solicitacao": pedido.data["id"], "aprovar": True})
        self.assertEqual(proprio.status_code, status.HTTP_403_FORBIDDEN)

        self.autenticar(self.consulado.responsavel)
        pendentes = self.client.get(f"/api/v1/consulados/{self.consulado.id}/solicitacoes-entrada/")
        self.assertEqual([p["id"] for p in pendentes.data], [pedido.data["id"]])
        aprovado = self.client.post(f"/api/v1/consulados/{self.consulado.id}/responder-entrada/",
                                    {"solicitacao": pedido.data["id"], "aprovar": True})
        self.assertEqual(aprovado.status_code, status.HTTP_200_OK, aprovado.data)
        self.assertTrue(MembroConsulado.objects.filter(usuario=self.torcedor, consulado=self.consulado).exists())


class PresencaEventoTests(BaseAPITestCase):
    def setUp(self):
        super().setUp()
        self.torcedor = criar_usuario()
        self.consulado = criar_consulado()
        self.evento = criar_evento(self.consulado)
        self.autenticar(self.torcedor)

    def test_nao_membro_confirma_presenca_em_evento_livre(self):
        resposta = self.client.post("/api/v1/presencas-evento/", {"evento": self.evento.id})
        self.assertEqual(resposta.status_code, status.HTTP_201_CREATED, resposta.data)

    def test_nao_membro_nao_confirma_presenca_em_evento_exclusivo(self):
        exclusivo = criar_evento(self.consulado, exclusivo_membros=True)
        resposta = self.client.post("/api/v1/presencas-evento/", {"evento": exclusivo.id})
        self.assertEqual(resposta.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("evento", resposta.data)

    def test_evento_exclusivo_nao_aparece_para_nao_membro(self):
        exclusivo = criar_evento(self.consulado, titulo="Só para membros", exclusivo_membros=True)
        ids = [e["id"] for e in self.client.get("/api/v1/eventos/").data["results"]]
        self.assertIn(self.evento.id, ids)
        self.assertNotIn(exclusivo.id, ids)
        MembroConsulado.objects.create(usuario=self.torcedor, consulado=self.consulado)
        ids = [e["id"] for e in self.client.get("/api/v1/eventos/").data["results"]]
        self.assertIn(exclusivo.id, ids)

    def test_membro_confirma_presenca_uma_unica_vez(self):
        MembroConsulado.objects.create(usuario=self.torcedor, consulado=self.consulado)
        primeira = self.client.post("/api/v1/presencas-evento/", {"evento": self.evento.id})
        self.assertEqual(primeira.status_code, status.HTTP_201_CREATED, primeira.data)
        segunda = self.client.post("/api/v1/presencas-evento/", {"evento": self.evento.id})
        self.assertEqual(segunda.status_code, status.HTTP_400_BAD_REQUEST)


class PermissoesTests(BaseAPITestCase):
    def test_torcedor_solicita_consulado_e_aprovacao_o_torna_embaixador(self):
        torcedor = criar_usuario()
        self.autenticar(torcedor)
        dados = {"nome": "Novo", "endereco": "Rua X", "latitude": "-7.1", "longitude": "-34.8",
                 "link_whatsapp": "https://chat.whatsapp.com/novo"}
        resposta = self.client.post("/api/v1/consulados/", dados)
        self.assertEqual(resposta.status_code, status.HTTP_201_CREATED, resposta.data)
        self.assertEqual(resposta.data["status_aprovacao"], StatusAprovacao.PENDENTE)
        # Só uma solicitação em análise por vez.
        segunda = self.client.post("/api/v1/consulados/", {**dados, "nome": "Outro"})
        self.assertEqual(segunda.status_code, status.HTTP_400_BAD_REQUEST)

        self.autenticar(criar_usuario(TipoUsuario.ADMIN))
        aprovado = self.client.post(f"/api/v1/consulados/{resposta.data['id']}/aprovar/")
        self.assertEqual(aprovado.status_code, status.HTTP_200_OK, aprovado.data)
        torcedor.refresh_from_db()
        self.assertEqual(torcedor.tipo_usuario, TipoUsuario.RESPONSAVEL_CONSULADO)

    def test_responsavel_por_aliado_nao_solicita_consulado(self):
        self.autenticar(criar_usuario(TipoUsuario.RESPONSAVEL_ALIADO))
        resposta = self.client.post("/api/v1/consulados/", {
            "nome": "Novo", "endereco": "Rua X", "latitude": "-7.1", "longitude": "-34.8",
        })
        self.assertEqual(resposta.status_code, status.HTTP_400_BAD_REQUEST)

    def test_evento_do_responsavel_nasce_publicado_e_edicao_mantem(self):
        responsavel = criar_usuario(TipoUsuario.RESPONSAVEL_CONSULADO)
        consulado = criar_consulado(responsavel=responsavel)
        self.autenticar(responsavel)
        inicio = timezone.now() + timedelta(days=2)
        resposta = self.client.post("/api/v1/eventos/", {
            "consulado": consulado.id, "titulo": "Resenha",
            "data_hora_inicio": inicio.isoformat(), "data_hora_fim": (inicio + timedelta(hours=3)).isoformat(),
        })
        self.assertEqual(resposta.status_code, status.HTTP_201_CREATED, resposta.data)
        self.assertEqual(resposta.data["status_aprovacao"], StatusAprovacao.APROVADO)
        editado = self.client.patch(f"/api/v1/eventos/{resposta.data['id']}/", {"titulo": "Resenha pré-jogo"})
        self.assertEqual(editado.data["status_aprovacao"], StatusAprovacao.APROVADO)

    def test_responsavel_cria_consulado_pendente_e_admin_aprova(self):
        responsavel = criar_usuario(TipoUsuario.RESPONSAVEL_CONSULADO)
        self.autenticar(responsavel)
        resposta = self.client.post("/api/v1/consulados/", {
            "nome": "Consulado Tambaú", "endereco": "Av. Tamandaré", "latitude": "-7.1", "longitude": "-34.8",
            "link_whatsapp": "https://chat.whatsapp.com/tambau",
        })
        self.assertEqual(resposta.status_code, status.HTTP_201_CREATED, resposta.data)
        self.assertEqual(resposta.data["status_aprovacao"], StatusAprovacao.PENDENTE)

        consulado_id = resposta.data["id"]
        self.assertEqual(
            self.client.post(f"/api/v1/consulados/{consulado_id}/aprovar/").status_code,
            status.HTTP_403_FORBIDDEN,
        )

        self.autenticar(criar_usuario(TipoUsuario.ADMIN))
        aprovacao = self.client.post(f"/api/v1/consulados/{consulado_id}/aprovar/")
        self.assertEqual(aprovacao.status_code, status.HTTP_200_OK)
        self.assertEqual(aprovacao.data["status_aprovacao"], StatusAprovacao.APROVADO)

    def test_torcedor_nao_cria_partida(self):
        self.autenticar(criar_usuario())
        resposta = self.client.post("/api/v1/partidas/", {
            "adversario": "X", "mando_campo": "CASA", "campeonato": "Y", "data_hora": "2030-01-01T16:00:00-03:00",
        })
        self.assertEqual(resposta.status_code, status.HTTP_403_FORBIDDEN)
