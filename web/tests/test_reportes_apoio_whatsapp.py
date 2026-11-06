"""WhatsApp só para membros, reportes de problemas/sugestões, página de apoio (Pix) e fim do check-in."""
from __future__ import annotations

from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import NoReverseMatch, reverse

from core.models import MembroConsulado, Reporte, TipoUsuario
from core.tests.factories import criar_consulado, criar_partida, criar_usuario
from web.pix import _crc16

LINK = "https://chat.whatsapp.com/GrupoSecreto"


class WhatsappSoParaMembrosTests(TestCase):
    def setUp(self):
        self.consulado = criar_consulado(link_whatsapp=LINK)
        self.membro = criar_usuario()
        MembroConsulado.objects.create(usuario=self.membro, consulado=self.consulado)
        self.visitante = criar_usuario()

    def _pagina(self, usuario):
        self.client.force_login(usuario)
        return self.client.get(reverse("web:consulado", args=[self.consulado.pk]))

    def _dados_do_mapa(self, usuario):
        self.client.force_login(usuario)
        pagina = self.client.get(reverse("web:consulados"))
        return {c["id"]: c for c in pagina.context["consulados"]}[self.consulado.pk]

    def test_nao_membro_nao_ve_o_link(self):
        pagina = self._pagina(self.visitante)
        self.assertNotContains(pagina, LINK)
        self.assertContains(pagina, "O grupo do WhatsApp é exclusivo para membros do consulado.")
        dados = self._dados_do_mapa(self.visitante)
        self.assertEqual(dados["whatsapp"], "")
        self.assertTrue(dados["whatsapp_so_membros"])
        self.assertNotContains(self.client.get(reverse("web:consulados")), LINK)

    def test_membro_embaixador_e_admin_veem_o_link(self):
        for usuario in (self.membro, self.consulado.responsavel, criar_usuario(TipoUsuario.ADMIN)):
            self.assertContains(self._pagina(usuario), LINK)
            self.assertEqual(self._dados_do_mapa(usuario)["whatsapp"], LINK)

    def test_api_esconde_o_link_de_quem_nao_e_membro(self):
        cache.clear()
        url = f"/api/v1/consulados/{self.consulado.pk}/"
        for usuario, esperado in ((self.visitante, ""), (self.membro, LINK)):
            resposta = self.client.post("/api/v1/auth/login/", {"email": usuario.email, "password": "SenhaForte#123"})
            token = resposta.json()["access"]
            dados = self.client.get(url, HTTP_AUTHORIZATION=f"Bearer {token}").json()
            self.assertEqual(dados["link_whatsapp"], esperado, usuario)


class ReportesTests(TestCase):
    def setUp(self):
        self.torcedor = criar_usuario()
        self.admin = criar_usuario(TipoUsuario.ADMIN)

    def _enviar(self, **dados):
        self.client.force_login(self.torcedor)
        return self.client.post(reverse("web:reportar"), {
            "tipo": "PROBLEMA", "mensagem": "O mapa não carrega no meu celular.", **dados,
        })

    def test_usuario_envia_e_so_admin_ve(self):
        resposta = self._enviar(pagina="/partidas/")
        self.assertRedirects(resposta, reverse("web:reportar"), fetch_redirect_response=False)
        reporte = Reporte.objects.get()
        self.assertEqual((reporte.usuario, reporte.tipo, reporte.pagina), (self.torcedor, "PROBLEMA", "/partidas/"))

        for usuario in (self.torcedor, criar_usuario(TipoUsuario.RESPONSAVEL_CONSULADO)):
            self.client.force_login(usuario)
            self.assertEqual(self.client.get(reverse("web:reportes")).status_code, 403)
        self.client.force_login(self.admin)
        lista = self.client.get(reverse("web:reportes"))
        self.assertContains(lista, "O mapa não carrega no meu celular.")
        self.assertContains(lista, self.torcedor.email)

    def test_mensagem_curta_e_recusada(self):
        self._enviar(mensagem="ruim")
        self.assertFalse(Reporte.objects.exists())

    def test_pagina_de_outro_site_nao_e_anexada(self):
        self._enviar(pagina="https://site-malicioso.com/")
        self.assertEqual(Reporte.objects.get().pagina, "")

    def test_admin_resolve_e_reabre(self):
        self._enviar()
        reporte = Reporte.objects.get()
        self.client.force_login(self.admin)
        self.assertContains(self.client.get(reverse("web:painel")), reverse("web:reportes"))
        self.client.post(reverse("web:responder-reporte", args=[reporte.pk]), {"acao": "resolver"})
        reporte.refresh_from_db()
        self.assertEqual((reporte.status, reporte.resolvido_por), (Reporte.Status.RESOLVIDO, self.admin))
        # Resolvidos saem da lista padrão (abertos) e aparecem no filtro.
        self.assertNotContains(self.client.get(reverse("web:reportes")), "O mapa não carrega")
        self.assertContains(self.client.get(reverse("web:reportes"), {"status": "RESOLVIDO"}), "O mapa não carrega")
        self.client.post(reverse("web:responder-reporte", args=[reporte.pk]), {"acao": "reabrir"})
        reporte.refresh_from_db()
        self.assertEqual(reporte.status, Reporte.Status.ABERTO)

    def test_nao_admin_nao_resolve(self):
        self._enviar()
        reporte = Reporte.objects.get()
        self.client.force_login(self.torcedor)
        self.assertEqual(self.client.post(reverse("web:responder-reporte", args=[reporte.pk])).status_code, 403)

    def test_link_no_menu(self):
        self.client.force_login(self.torcedor)
        pagina = self.client.get(reverse("web:partidas"))
        self.assertContains(pagina, reverse("web:reportar"))
        self.assertContains(pagina, reverse("web:apoie"))


class ApoieTests(TestCase):
    def setUp(self):
        self.client.force_login(criar_usuario())

    def test_pagina_mostra_pix_ficticio_com_aviso_e_qr(self):
        pagina = self.client.get(reverse("web:apoie"))
        self.assertContains(pagina, "Chave Pix fictícia.")
        self.assertContains(pagina, "<svg")
        codigo = pagina.context["codigo_pix"]
        self.assertTrue(codigo.startswith("000201"))
        self.assertIn("br.gov.bcb.pix", codigo)
        self.assertEqual(codigo[-4:], _crc16(codigo[:-4]))  # CRC confere

    def test_valor_sugerido_entra_no_codigo(self):
        pagina = self.client.get(reverse("web:apoie"), {"valor": "25"})
        self.assertIn("540525.00", pagina.context["codigo_pix"])

    def test_valor_invalido_e_ignorado(self):
        pagina = self.client.get(reverse("web:apoie"), {"valor": "-5"})
        self.assertNotIn("5404", pagina.context["codigo_pix"])

    @override_settings(CONEXAO_CORAL={"PIX": {"chave": "chave@real.com", "nome": "Conexao Coral", "cidade": "Recife",
                                              "ficticio": False}, "REQUISITOS_CONSULADO": []})
    def test_chave_real_tira_o_aviso(self):
        self.assertNotContains(self.client.get(reverse("web:apoie")), "Chave Pix fictícia.")


class SemCheckinTests(TestCase):
    def test_rotas_de_checkin_nao_existem(self):
        for nome in ("web:fazer-checkin", "web:cancelar-checkin"):
            with self.assertRaises(NoReverseMatch):
                reverse(nome, args=[1])

    def test_api_nao_tem_checkin(self):
        cache.clear()
        usuario = criar_usuario()
        token = self.client.post("/api/v1/auth/login/", {"email": usuario.email, "password": "SenhaForte#123"}).json()["access"]
        resposta = self.client.get("/api/v1/checkins/", HTTP_AUTHORIZATION=f"Bearer {token}")
        self.assertEqual(resposta.status_code, 404)

    def test_pagina_do_consulado_sem_checkin(self):
        consulado = criar_consulado()
        criar_partida()
        self.client.force_login(criar_usuario())
        pagina = self.client.get(reverse("web:consulado", args=[consulado.pk]))
        self.assertContains(pagina, "Próximo jogo do Santa Cruz")
        self.assertNotContains(pagina, "Fazer check-in")
        self.assertNotIn("meu_checkin", pagina.context.keys())
