"""Testes de integração das principais regras de negócio via API."""
from __future__ import annotations

from django.core.cache import cache
from rest_framework import status
from rest_framework.test import APITestCase

from core.models import CheckIn, MembroConsulado, StatusAprovacao, TipoUsuario, TokenWhitelist
from core.tests.factories import criar_consulado, criar_evento, criar_partida, criar_usuario


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


class CheckInTests(BaseAPITestCase):
    def setUp(self):
        super().setUp()
        self.torcedor = criar_usuario()
        self.consulado = criar_consulado()
        self.partida = criar_partida()
        self.autenticar(self.torcedor)

    def _checkin(self, consulado=None):
        return self.client.post("/api/v1/checkins/", {
            "partida": self.partida.id, "consulado": (consulado or self.consulado).id,
        })

    def test_primeiro_checkin_filia_usuario_ao_consulado(self):
        self.assertFalse(MembroConsulado.objects.filter(usuario=self.torcedor).exists())
        resposta = self._checkin()
        self.assertEqual(resposta.status_code, status.HTTP_201_CREATED, resposta.data)
        self.assertTrue(
            MembroConsulado.objects.filter(usuario=self.torcedor, consulado=self.consulado).exists()
        )

    def test_apenas_um_checkin_ativo_por_partida(self):
        self.assertEqual(self._checkin().status_code, status.HTTP_201_CREATED)
        outro = criar_consulado()
        resposta = self._checkin(outro)
        self.assertEqual(resposta.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("partida", resposta.data)

    def test_cancelar_libera_novo_checkin(self):
        checkin_id = self._checkin().data["id"]
        self.assertEqual(
            self.client.post(f"/api/v1/checkins/{checkin_id}/cancelar/").status_code, status.HTTP_200_OK,
        )
        self.assertEqual(self._checkin(criar_consulado()).status_code, status.HTTP_201_CREATED)
        self.assertEqual(CheckIn.objects.filter(usuario=self.torcedor, ativo=True).count(), 1)

    def test_nao_permite_checkin_em_consulado_pendente(self):
        pendente = criar_consulado(status_aprovacao=StatusAprovacao.PENDENTE)
        self.assertEqual(self._checkin(pendente).status_code, status.HTTP_400_BAD_REQUEST)


class PresencaEventoTests(BaseAPITestCase):
    def setUp(self):
        super().setUp()
        self.torcedor = criar_usuario()
        self.consulado = criar_consulado()
        self.evento = criar_evento(self.consulado)
        self.autenticar(self.torcedor)

    def test_nao_membro_nao_confirma_presenca(self):
        resposta = self.client.post("/api/v1/presencas-evento/", {"evento": self.evento.id})
        self.assertEqual(resposta.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("evento", resposta.data)

    def test_membro_confirma_presenca_uma_unica_vez(self):
        MembroConsulado.objects.create(usuario=self.torcedor, consulado=self.consulado)
        primeira = self.client.post("/api/v1/presencas-evento/", {"evento": self.evento.id})
        self.assertEqual(primeira.status_code, status.HTTP_201_CREATED, primeira.data)
        segunda = self.client.post("/api/v1/presencas-evento/", {"evento": self.evento.id})
        self.assertEqual(segunda.status_code, status.HTTP_400_BAD_REQUEST)


class PermissoesTests(BaseAPITestCase):
    def test_torcedor_nao_cria_consulado(self):
        self.autenticar(criar_usuario())
        resposta = self.client.post("/api/v1/consulados/", {
            "nome": "Novo", "endereco": "Rua X", "latitude": "-7.1", "longitude": "-34.8",
        })
        self.assertEqual(resposta.status_code, status.HTTP_403_FORBIDDEN)

    def test_responsavel_cria_consulado_pendente_e_admin_aprova(self):
        responsavel = criar_usuario(TipoUsuario.RESPONSAVEL_CONSULADO)
        self.autenticar(responsavel)
        resposta = self.client.post("/api/v1/consulados/", {
            "nome": "Consulado Tambaú", "endereco": "Av. Tamandaré", "latitude": "-7.1", "longitude": "-34.8",
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
