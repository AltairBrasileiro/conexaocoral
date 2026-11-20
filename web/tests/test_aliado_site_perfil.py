"""Vitrine da Torcida: botão "Site" e foto de perfil do negócio."""
from __future__ import annotations

from django.test import TestCase, override_settings
from django.urls import reverse

from core.models import Aliado, StatusAprovacao, TipoUsuario
from core.tests.factories import criar_usuario
from web.tests.test_icone_lojista_admin import MEDIA_TESTE, criar_aliado, imagem_png


@override_settings(MEDIA_ROOT=MEDIA_TESTE)
class SiteEFotoDePerfilTests(TestCase):
    def setUp(self):
        self.lojista = criar_usuario(TipoUsuario.RESPONSAVEL_ALIADO)
        self.client.force_login(self.lojista)

    def _dados(self, **extra):
        return {"nome_negocio": "Camisas Coral", "categoria": "VESTUARIO", "descricao": "Camisas da torcida.", **extra}

    def test_cadastra_com_site_e_foto_de_perfil(self):
        self.client.post(reverse("web:novo-negocio"), self._dados(
            link_site="https://www.camisascoral.com.br", foto_perfil=imagem_png("logo.png"),
        ))
        aliado = Aliado.objects.get()
        self.assertEqual(aliado.link_site, "https://www.camisascoral.com.br")
        self.assertTrue(aliado.foto_perfil.name.startswith("aliados/perfil/"))

    def test_site_invalido_e_recusado(self):
        resposta = self.client.post(reverse("web:novo-negocio"), self._dados(link_site="não é um site"))
        self.assertContains(resposta, "Informe um endereço válido")
        self.assertFalse(Aliado.objects.exists())

    def test_aceita_os_atalhos_digitados_no_celular(self):
        self.client.post(reverse("web:novo-negocio"), self._dados(
            link_instagram="@camisas.coral", link_whatsapp="(81) 99999-8888", link_site="www.camisascoral.com.br",
        ))
        aliado = Aliado.objects.get()
        self.assertEqual(aliado.link_instagram, "https://instagram.com/camisas.coral")
        self.assertEqual(aliado.link_whatsapp, "https://wa.me/5581999998888")
        self.assertEqual(aliado.link_site, "https://www.camisascoral.com.br")

    def test_links_completos_continuam_iguais(self):
        self.client.post(reverse("web:novo-negocio"), self._dados(
            link_instagram="https://www.instagram.com/camisascoral/", link_whatsapp="https://wa.me/5581999998888",
            link_site="http://camisascoral.com.br/loja",
        ))
        aliado = Aliado.objects.get()
        self.assertEqual(aliado.link_instagram, "https://www.instagram.com/camisascoral/")
        self.assertEqual(aliado.link_whatsapp, "https://wa.me/5581999998888")
        self.assertEqual(aliado.link_site, "http://camisascoral.com.br/loja")

    def test_campos_de_link_abrem_o_teclado_certo_no_celular(self):
        resposta = self.client.get(reverse("web:novo-negocio"))
        self.assertContains(resposta, 'inputmode="tel"')
        self.assertContains(resposta, 'autocapitalize="none"')
        self.assertContains(resposta, "campo-imagem--perfil")

    def test_vitrine_mostra_botao_site_e_foto_de_perfil(self):
        aliado = criar_aliado(self.lojista, link_site="https://www.bardoarruda.com.br", foto_perfil=imagem_png())
        resposta = self.client.get(reverse("web:aliados"))
        self.assertContains(resposta, 'href="https://www.bardoarruda.com.br"')
        self.assertContains(resposta, aliado.foto_perfil.url)

    def test_sem_site_o_botao_fica_desativado(self):
        criar_aliado(self.lojista)
        resposta = self.client.get(reverse("web:aliados"))
        self.assertContains(resposta, '<span class="icon">language</span>Site</button>', html=False)

    def test_troca_e_remove_a_foto_de_perfil_sem_mexer_na_foto_do_negocio(self):
        aliado = criar_aliado(self.lojista, foto=imagem_png(), foto_perfil=imagem_png("logo.png"),
                              status_aprovacao=StatusAprovacao.PENDENTE)
        foto, antiga, armazenamento = aliado.foto.name, aliado.foto_perfil.name, aliado.foto.storage
        url = reverse("web:editar-negocio", args=[aliado.pk])
        base = {"nome_negocio": aliado.nome_negocio, "categoria": aliado.categoria, "descricao": aliado.descricao}
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(url, {**base, "foto_perfil": imagem_png("nova.png")})
        aliado.refresh_from_db()
        self.assertNotEqual(aliado.foto_perfil.name, antiga)
        self.assertFalse(armazenamento.exists(antiga))
        nova = aliado.foto_perfil.name
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(url, {**base, "foto_perfil-clear": "on"})
        aliado.refresh_from_db()
        self.assertFalse(aliado.foto_perfil)
        self.assertFalse(armazenamento.exists(nova))
        self.assertEqual(aliado.foto.name, foto)
        self.assertTrue(armazenamento.exists(foto))

    def test_excluir_apaga_as_duas_imagens(self):
        aliado = criar_aliado(self.lojista, foto=imagem_png(), foto_perfil=imagem_png("logo.png"))
        arquivos, armazenamento = [aliado.foto.name, aliado.foto_perfil.name], aliado.foto.storage
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(reverse("web:excluir-negocio", args=[aliado.pk]))
        for arquivo in arquivos:
            self.assertFalse(armazenamento.exists(arquivo))
