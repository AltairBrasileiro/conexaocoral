"""Testes de upload de imagens (eventos e solicitação de consulado), lista de cargos e estáticos versionados."""
from __future__ import annotations

import io
import shutil
import tempfile
from datetime import timedelta

from django.core.files.uploadedfile import SimpleUploadedFile
from django.template import Context, Template
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from core.models import Consulado, Evento, FotoEvento, MembroConsulado, TipoUsuario
from core.services import EventoService
from core.tests.factories import criar_consulado, criar_evento, criar_usuario
from web.forms import OUTRO_CARGO

MEDIA_TESTE = tempfile.mkdtemp(prefix="coral-media-testes-")


def tearDownModule():
    shutil.rmtree(MEDIA_TESTE, ignore_errors=True)


def imagem_png(nome: str = "foto.png") -> SimpleUploadedFile:
    buffer = io.BytesIO()
    Image.new("RGB", (40, 30), (227, 6, 19)).save(buffer, format="PNG")
    return SimpleUploadedFile(nome, buffer.getvalue(), content_type="image/png")


@override_settings(MEDIA_ROOT=MEDIA_TESTE)
class ImagemEventoTests(TestCase):
    def setUp(self):
        self.embaixador = criar_usuario(TipoUsuario.RESPONSAVEL_CONSULADO)
        self.consulado = criar_consulado(responsavel=self.embaixador)
        self.client.force_login(self.embaixador)

    def _dados(self, **extra):
        inicio = timezone.localtime() + timedelta(days=2)
        return {"titulo": "Resenha", "inicio": inicio.strftime("%Y-%m-%dT%H:%M"), "duracao": "3", **extra}

    def test_cria_evento_com_varias_fotos_e_exibe_na_pagina_publica(self):
        self.client.post(reverse("web:novo-evento", args=[self.consulado.pk]),
                         self._dados(fotos=[imagem_png("a.png"), imagem_png("b.png"), imagem_png("c.png")]))
        evento = Evento.objects.get(titulo="Resenha")
        fotos = list(evento.fotos.all())
        self.assertEqual(len(fotos), 3)
        self.assertEqual([f.ordem for f in fotos], [0, 1, 2])
        self.assertTrue(all(f.imagem.name.startswith("eventos/") for f in fotos))
        self.assertNotIn("a.png", fotos[0].imagem.name)  # nome aleatório, não o do arquivo enviado
        self.client.force_login(criar_usuario())
        pagina = self.client.get(reverse("web:consulado", args=[self.consulado.pk]))
        for foto in fotos:
            self.assertContains(pagina, foto.imagem.url)

    def test_editar_adiciona_e_remove_fotos(self):
        evento = criar_evento(self.consulado)
        primeira = FotoEvento.objects.create(evento=evento, imagem=imagem_png(), ordem=0)
        segunda = FotoEvento.objects.create(evento=evento, imagem=imagem_png(), ordem=1)
        arquivo_removido = primeira.imagem.name
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(reverse("web:editar-evento", args=[evento.pk]), self._dados(
                remover_fotos=[str(primeira.pk)], fotos=[imagem_png("nova.png")],
            ))
        fotos = list(evento.fotos.all())
        self.assertEqual(len(fotos), 2)
        self.assertEqual(fotos[0].pk, segunda.pk)
        self.assertFalse(primeira.imagem.storage.exists(arquivo_removido))

    def test_editar_sem_enviar_mantem_as_fotos(self):
        evento = criar_evento(self.consulado)
        FotoEvento.objects.create(evento=evento, imagem=imagem_png(), ordem=0)
        self.client.post(reverse("web:editar-evento", args=[evento.pk]), self._dados(titulo="Resenha 2"))
        evento.refresh_from_db()
        self.assertEqual(evento.titulo, "Resenha 2")
        self.assertEqual(evento.fotos.count(), 1)

    def test_limite_de_fotos_por_evento(self):
        maximo = EventoService.MAXIMO_FOTOS
        resposta = self.client.post(reverse("web:novo-evento", args=[self.consulado.pk]),
                                    self._dados(fotos=[imagem_png(f"{i}.png") for i in range(maximo + 1)]))
        self.assertContains(resposta, f"Cada evento pode ter até {maximo} fotos")
        self.assertFalse(Evento.objects.exists())

    def test_excluir_evento_apaga_os_arquivos(self):
        evento = criar_evento(self.consulado)
        foto = FotoEvento.objects.create(evento=evento, imagem=imagem_png(), ordem=0)
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(reverse("web:excluir-evento", args=[evento.pk]))
        self.assertFalse(foto.imagem.storage.exists(foto.imagem.name))

    def test_arquivo_que_nao_e_imagem_e_recusado(self):
        falso = SimpleUploadedFile("cartaz.jpg", b"nao sou uma imagem", content_type="image/jpeg")
        resposta = self.client.post(reverse("web:novo-evento", args=[self.consulado.pk]), self._dados(fotos=[falso]))
        self.assertEqual(resposta.status_code, 200)
        self.assertFalse(Evento.objects.exists())

    def test_formato_nao_permitido_e_recusado(self):
        buffer = io.BytesIO()
        Image.new("RGB", (10, 10)).save(buffer, format="GIF")
        gif = SimpleUploadedFile("anim.gif", buffer.getvalue(), content_type="image/gif")
        resposta = self.client.post(reverse("web:novo-evento", args=[self.consulado.pk]), self._dados(fotos=[gif]))
        self.assertContains(resposta, "Envie uma imagem JPG, PNG ou WebP.")


@override_settings(MEDIA_ROOT=MEDIA_TESTE)
class FotoSolicitacaoTests(TestCase):
    def test_foto_do_local_vai_para_a_galeria_e_aparece_para_o_admin(self):
        torcedor = criar_usuario()
        self.client.force_login(torcedor)
        self.client.post(reverse("web:solicitar-consulado"), {
            "nome": "Consulado Coral Gravatá", "endereco": "Rua A, 1 - Gravatá, PE",
            "latitude": "-8.201000", "longitude": "-35.565000", "aceite_requisitos": "on", "link_whatsapp": "https://chat.whatsapp.com/teste",
            "foto": imagem_png("fachada.png"),
        })
        consulado = Consulado.objects.get(nome="Consulado Coral Gravatá")
        foto = consulado.fotos.get()
        self.assertTrue(foto.imagem.name.startswith("consulados/"))
        self.assertEqual(foto.src, foto.imagem.url)
        self.client.force_login(criar_usuario(TipoUsuario.ADMIN))
        self.assertContains(self.client.get(reverse("web:solicitacoes")), foto.imagem.url)

    def test_foto_e_opcional(self):
        self.client.force_login(criar_usuario())
        self.client.post(reverse("web:solicitar-consulado"), {
            "nome": "Consulado Coral Bezerros", "endereco": "Rua B, 2 - Bezerros, PE",
            "latitude": "-8.233000", "longitude": "-35.797000", "aceite_requisitos": "on", "link_whatsapp": "https://chat.whatsapp.com/teste",
        })
        self.assertFalse(Consulado.objects.get(nome="Consulado Coral Bezerros").fotos.exists())


class CargoTests(TestCase):
    def setUp(self):
        self.embaixador = criar_usuario(TipoUsuario.RESPONSAVEL_CONSULADO)
        self.consulado = criar_consulado(responsavel=self.embaixador)
        self.membro = MembroConsulado.objects.create(usuario=criar_usuario(nome="Ana"), consulado=self.consulado)
        self.client.force_login(self.embaixador)
        self.url = reverse("web:definir-cargo", args=[self.membro.pk])

    def test_pagina_lista_as_opcoes_de_cargo_sem_iniciais(self):
        pagina = self.client.get(reverse("web:membros", args=[self.consulado.pk]))
        self.assertContains(pagina, '<option value="Tesoureiro(a)">Tesoureiro(a)</option>', html=True)
        self.assertContains(pagina, "Outro cargo…")
        self.assertNotContains(pagina, "membro__avatar")

    def test_escolhe_cargo_da_lista(self):
        self.client.post(self.url, {"cargo": "Secretário(a)"})
        self.membro.refresh_from_db()
        self.assertEqual(self.membro.cargo, "Secretário(a)")

    def test_outro_cargo_digitado(self):
        self.client.post(self.url, {"cargo": OUTRO_CARGO, "cargo_outro": "Mestre de bateria"})
        self.membro.refresh_from_db()
        self.assertEqual(self.membro.cargo, "Mestre de bateria")
        # O cargo personalizado continua selecionado na lista.
        pagina = self.client.get(reverse("web:membros", args=[self.consulado.pk]))
        self.assertContains(pagina, '<option value="Mestre de bateria" selected>Mestre de bateria</option>', html=True)

    def test_outro_cargo_vazio_e_recusado(self):
        self.membro.cargo = "Tesoureira"
        self.membro.save()
        self.client.post(self.url, {"cargo": OUTRO_CARGO, "cargo_outro": ""})
        self.membro.refresh_from_db()
        self.assertEqual(self.membro.cargo, "Tesoureira")

    def test_cadastrar_membro_com_outro_cargo(self):
        criar_usuario(email="bia@coral.com")
        self.client.post(reverse("web:membros", args=[self.consulado.pk]), {
            "email": "bia@coral.com", "cargo": OUTRO_CARGO, "cargo_outro": "Fotógrafa",
        })
        self.assertEqual(MembroConsulado.objects.get(usuario__email="bia@coral.com").cargo, "Fotógrafa")


class EstaticoVersionadoTests(TestCase):
    def test_url_leva_a_data_de_modificacao(self):
        html = Template("{% load coral %}{% estatico 'web/coral.css' %}").render(Context())
        self.assertRegex(html, r"^/static/web/coral\.css\?v=\d+$")
