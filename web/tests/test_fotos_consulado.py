"""Edição das fotos do consulado no Painel: só o embaixador ou membros com cargo."""
from __future__ import annotations

import io
import shutil
import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from core.models import FotoConsulado, MembroConsulado, TipoUsuario
from core.services import ConsuladoService
from core.tests.factories import criar_consulado, criar_usuario

MEDIA_TESTE = tempfile.mkdtemp(prefix="coral-media-fotos-")


def tearDownModule():
    shutil.rmtree(MEDIA_TESTE, ignore_errors=True)


def imagem_png(nome: str = "foto.png") -> SimpleUploadedFile:
    buffer = io.BytesIO()
    Image.new("RGB", (40, 30), (11, 11, 11)).save(buffer, format="PNG")
    return SimpleUploadedFile(nome, buffer.getvalue(), content_type="image/png")


@override_settings(MEDIA_ROOT=MEDIA_TESTE)
class PermissaoFotosTests(TestCase):
    def setUp(self):
        self.embaixador = criar_usuario(TipoUsuario.RESPONSAVEL_CONSULADO)
        self.consulado = criar_consulado(responsavel=self.embaixador)
        self.diretor = criar_usuario(nome="Diretora")
        MembroConsulado.objects.create(usuario=self.diretor, consulado=self.consulado, cargo="Diretor(a) social")
        self.membro_sem_cargo = criar_usuario()
        MembroConsulado.objects.create(usuario=self.membro_sem_cargo, consulado=self.consulado)
        self.url = reverse("web:fotos-consulado", args=[self.consulado.pk])

    def _enviar(self, usuario, **extra):
        self.client.force_login(usuario)
        return self.client.post(self.url, {"imagem": imagem_png(), "legenda": "Telão", **extra})

    def test_embaixador_envia_foto(self):
        self._enviar(self.embaixador)
        foto = FotoConsulado.objects.get(consulado=self.consulado)
        self.assertEqual(foto.legenda, "Telão")
        self.assertTrue(foto.imagem.name.startswith("consulados/"))

    def test_membro_com_cargo_envia_foto(self):
        resposta = self._enviar(self.diretor)
        self.assertRedirects(resposta, self.url, fetch_redirect_response=False)
        self.assertTrue(FotoConsulado.objects.filter(consulado=self.consulado).exists())

    def test_membro_sem_cargo_nao_acessa(self):
        self.client.force_login(self.membro_sem_cargo)
        self.assertEqual(self.client.get(self.url).status_code, 403)
        self.assertEqual(self._enviar(self.membro_sem_cargo).status_code, 403)
        self.assertFalse(FotoConsulado.objects.exists())

    def test_torcedor_de_fora_e_admin_nao_acessam(self):
        for usuario in (criar_usuario(), criar_usuario(TipoUsuario.ADMIN)):
            self.client.force_login(usuario)
            self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_cargo_em_outro_consulado_nao_vale(self):
        outro = criar_consulado()
        MembroConsulado.objects.create(usuario=self.membro_sem_cargo, consulado=outro, cargo="Tesoureiro(a)")
        self.client.force_login(self.membro_sem_cargo)
        self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_perder_o_cargo_tira_o_acesso(self):
        filiacao = MembroConsulado.objects.get(usuario=self.diretor)
        filiacao.cargo = ""
        filiacao.save()
        self.client.force_login(self.diretor)
        self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_acoes_de_foto_respeitam_a_permissao(self):
        foto = FotoConsulado.objects.create(consulado=self.consulado, url="https://exemplo.com/a.jpg")
        self.client.force_login(self.membro_sem_cargo)
        for nome in ("web:legenda-foto", "web:capa-foto", "web:remover-foto"):
            self.assertEqual(self.client.post(reverse(nome, args=[foto.pk]), {"legenda": "x"}).status_code, 403)
        self.assertTrue(FotoConsulado.objects.filter(pk=foto.pk).exists())


@override_settings(MEDIA_ROOT=MEDIA_TESTE)
class AcoesFotosTests(TestCase):
    def setUp(self):
        self.embaixador = criar_usuario(TipoUsuario.RESPONSAVEL_CONSULADO)
        self.consulado = criar_consulado(responsavel=self.embaixador)
        self.client.force_login(self.embaixador)

    def test_legenda_capa_e_remocao(self):
        primeira = FotoConsulado.objects.create(consulado=self.consulado, url="https://exemplo.com/1.jpg", ordem=0)
        segunda = FotoConsulado.objects.create(consulado=self.consulado, imagem=imagem_png(), ordem=1)
        self.client.post(reverse("web:legenda-foto", args=[segunda.pk]), {"legenda": "Fachada"})
        self.client.post(reverse("web:capa-foto", args=[segunda.pk]))
        ordem = list(self.consulado.fotos.values_list("pk", flat=True))
        self.assertEqual(ordem, [segunda.pk, primeira.pk])
        segunda.refresh_from_db()
        self.assertEqual(segunda.legenda, "Fachada")

        arquivo = segunda.imagem.name
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(reverse("web:remover-foto", args=[segunda.pk]))
        self.assertFalse(FotoConsulado.objects.filter(pk=segunda.pk).exists())
        self.assertFalse(segunda.imagem.storage.exists(arquivo))

    def test_limite_de_fotos(self):
        for i in range(ConsuladoService.MAXIMO_FOTOS):
            FotoConsulado.objects.create(consulado=self.consulado, url=f"https://exemplo.com/{i}.jpg", ordem=i)
        resposta = self.client.post(reverse("web:fotos-consulado", args=[self.consulado.pk]), {"imagem": imagem_png()})
        self.assertContains(resposta, "fotos, o máximo")
        self.assertEqual(self.consulado.fotos.count(), ConsuladoService.MAXIMO_FOTOS)


class PainelDoMembroComCargoTests(TestCase):
    def setUp(self):
        self.consulado = criar_consulado(nome="Consulado Coral Recife")
        self.diretor = criar_usuario()
        MembroConsulado.objects.create(usuario=self.diretor, consulado=self.consulado, cargo="Secretário(a)")

    def test_membro_com_cargo_ve_painel_so_com_fotos(self):
        self.client.force_login(self.diretor)
        self.assertContains(self.client.get(reverse("web:partidas")), reverse("web:painel"))
        painel = self.client.get(reverse("web:painel"))
        self.assertEqual(painel.status_code, 200)
        self.assertContains(painel, "Consulado Coral Recife")
        self.assertContains(painel, reverse("web:fotos-consulado", args=[self.consulado.pk]))
        # As demais configurações continuam só com o embaixador.
        self.assertNotContains(painel, reverse("web:editar-consulado", args=[self.consulado.pk]))
        self.assertNotContains(painel, reverse("web:membros", args=[self.consulado.pk]))
        self.assertNotContains(painel, reverse("web:novo-evento", args=[self.consulado.pk]))

    def test_torcedor_sem_cargo_nao_ve_painel(self):
        torcedor = criar_usuario()
        MembroConsulado.objects.create(usuario=torcedor, consulado=self.consulado)
        self.client.force_login(torcedor)
        self.assertNotContains(self.client.get(reverse("web:partidas")), reverse("web:painel"))
        self.assertEqual(self.client.get(reverse("web:painel")).status_code, 403)

    def test_embaixador_ve_fotos_no_painel(self):
        self.client.force_login(self.consulado.responsavel)
        painel = self.client.get(reverse("web:painel"))
        self.assertContains(painel, "Fotos do consulado")
        self.assertContains(painel, reverse("web:editar-consulado", args=[self.consulado.pk]))
