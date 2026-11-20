"""Ícone do consulado (pino do mapa), fluxo do lojista e telas de administração."""
from __future__ import annotations

import io
import shutil
import tempfile
from datetime import timedelta

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from core.models import Aliado, CategoriaAliado, MembroConsulado, Partida, StatusAprovacao, TipoUsuario
from core.services import AliadoService
from core.tests.factories import criar_consulado, criar_partida, criar_usuario

MEDIA_TESTE = tempfile.mkdtemp(prefix="coral-media-testes-")


def tearDownModule():
    shutil.rmtree(MEDIA_TESTE, ignore_errors=True)


def imagem_png(nome: str = "foto.png") -> SimpleUploadedFile:
    buffer = io.BytesIO()
    Image.new("RGB", (40, 40), (227, 6, 19)).save(buffer, format="PNG")
    return SimpleUploadedFile(nome, buffer.getvalue(), content_type="image/png")


def criar_aliado(usuario=None, **extra) -> Aliado:
    dados = {
        "nome_negocio": "Bar do Arruda", "categoria": CategoriaAliado.BAR, "descricao": "Petiscos e cerveja.",
        "status_aprovacao": StatusAprovacao.APROVADO,
    }
    dados.update(extra)
    return Aliado.objects.create(usuario=usuario or criar_usuario(TipoUsuario.RESPONSAVEL_ALIADO), **dados)


# ------------------------------------------------------------ ícone do consulado
@override_settings(MEDIA_ROOT=MEDIA_TESTE)
class IconeConsuladoTests(TestCase):
    def setUp(self):
        self.embaixador = criar_usuario(TipoUsuario.RESPONSAVEL_CONSULADO)
        self.consulado = criar_consulado(responsavel=self.embaixador)
        self.url = reverse("web:icone-consulado", args=[self.consulado.pk])
        self.remover = reverse("web:remover-icone-consulado", args=[self.consulado.pk])

    def _com_cargo(self, cargo="Tesoureiro(a)"):
        membro = criar_usuario()
        MembroConsulado.objects.create(usuario=membro, consulado=self.consulado, cargo=cargo)
        return membro

    def test_embaixador_envia_e_o_icone_vira_o_pino_do_mapa(self):
        self.client.force_login(self.embaixador)
        resposta = self.client.post(self.url, {"icone": imagem_png()})
        self.assertRedirects(resposta, self.url)
        self.consulado.refresh_from_db()
        self.assertTrue(self.consulado.logo.name.startswith("consulados/icones/"))
        mapa = self.client.get(reverse("web:consulados"))
        dados = next(c for c in mapa.context["consulados"] if c["id"] == self.consulado.pk)
        self.assertEqual(dados["logo"], self.consulado.logo.url)

    def test_trocar_apaga_o_arquivo_antigo(self):
        self.client.force_login(self.embaixador)
        self.client.post(self.url, {"icone": imagem_png()})
        self.consulado.refresh_from_db()
        antigo, armazenamento = self.consulado.logo.name, self.consulado.logo.storage
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(self.url, {"icone": imagem_png("novo.png")})
        self.consulado.refresh_from_db()
        self.assertNotEqual(self.consulado.logo.name, antigo)
        self.assertFalse(armazenamento.exists(antigo))

    def test_remover_volta_ao_pino_padrao(self):
        self.client.force_login(self.embaixador)
        self.client.post(self.url, {"icone": imagem_png()})
        self.consulado.refresh_from_db()
        arquivo, armazenamento = self.consulado.logo.name, self.consulado.logo.storage
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(self.remover)
        self.consulado.refresh_from_db()
        self.assertEqual(self.consulado.icone_url, "")
        self.assertFalse(armazenamento.exists(arquivo))

    def test_remover_tambem_limpa_o_link_antigo(self):
        self.consulado.logo_url = "https://exemplo.com/logo.png"
        self.consulado.save()
        self.client.force_login(self.embaixador)
        self.client.post(self.remover)
        self.consulado.refresh_from_db()
        self.assertEqual(self.consulado.logo_url, "")

    def test_membro_com_cargo_edita_e_ve_a_secao_no_painel(self):
        self.client.force_login(self._com_cargo())
        painel = self.client.get(reverse("web:painel"))
        self.assertContains(painel, self.url)
        self.client.post(self.url, {"icone": imagem_png()})
        self.consulado.refresh_from_db()
        self.assertTrue(self.consulado.logo)

    def test_membro_sem_cargo_e_estranho_nao_editam(self):
        sem_cargo = criar_usuario()
        MembroConsulado.objects.create(usuario=sem_cargo, consulado=self.consulado)
        for usuario in (sem_cargo, criar_usuario(), criar_usuario(TipoUsuario.RESPONSAVEL_CONSULADO)):
            self.client.force_login(usuario)
            self.assertEqual(self.client.get(self.url).status_code, 403)
            self.assertEqual(self.client.post(self.url, {"icone": imagem_png()}).status_code, 403)
            self.assertEqual(self.client.post(self.remover).status_code, 403)
        self.consulado.refresh_from_db()
        self.assertFalse(self.consulado.logo)

    def test_consulado_sem_aprovacao_nao_troca_o_icone(self):
        pendente = criar_consulado(responsavel=self.embaixador, status_aprovacao=StatusAprovacao.PENDENTE)
        self.client.force_login(self.embaixador)
        resposta = self.client.post(reverse("web:icone-consulado", args=[pendente.pk]), {"icone": imagem_png()})
        self.assertEqual(resposta.status_code, 403)

    def test_arquivo_que_nao_e_imagem_e_recusado(self):
        self.client.force_login(self.embaixador)
        falso = SimpleUploadedFile("logo.png", b"nao sou imagem", content_type="image/png")
        resposta = self.client.post(self.url, {"icone": falso})
        self.assertEqual(resposta.status_code, 200)
        self.consulado.refresh_from_db()
        self.assertFalse(self.consulado.logo)


class MapaSemBarraDeTotalTests(TestCase):
    def test_mapa_nao_anuncia_o_total_de_consulados(self):
        criar_consulado()
        self.client.force_login(criar_usuario())
        self.assertNotContains(self.client.get(reverse("web:consulados")), "no mapa</p>")
        from django.contrib.staticfiles import finders
        with open(finders.find("web/mapa.js"), encoding="utf-8") as arquivo:
            self.assertNotIn('" no mapa"', arquivo.read())


# ------------------------------------------------------------------- lojista
@override_settings(MEDIA_ROOT=MEDIA_TESTE)
class LojistaTests(TestCase):
    def setUp(self):
        self.lojista = criar_usuario(TipoUsuario.RESPONSAVEL_ALIADO)
        self.client.force_login(self.lojista)

    def _dados(self, **extra):
        return {
            "nome_negocio": "Camisas Coral", "categoria": "VESTUARIO", "descricao": "Camisas e bonés da torcida.",
            "link_instagram": "https://instagram.com/camisascoral", "link_whatsapp": "https://wa.me/5581999999999",
            **extra,
        }

    def test_cadastra_com_foto_e_fica_em_analise_fora_da_vitrine(self):
        resposta = self.client.post(reverse("web:novo-negocio"), self._dados(foto=imagem_png()))
        self.assertRedirects(resposta, reverse("web:meus-negocios"))
        aliado = Aliado.objects.get(nome_negocio="Camisas Coral")
        self.assertEqual(aliado.usuario, self.lojista)
        self.assertEqual(aliado.status_aprovacao, StatusAprovacao.PENDENTE)
        self.assertTrue(aliado.foto.name.startswith("aliados/"))
        self.assertContains(self.client.get(reverse("web:meus-negocios")), "Em análise")
        self.assertNotContains(self.client.get(reverse("web:aliados")), "Camisas Coral")

    def test_links_precisam_ser_do_instagram_e_do_whatsapp(self):
        resposta = self.client.post(reverse("web:novo-negocio"), self._dados(
            link_instagram="https://exemplo.com/x", link_whatsapp="https://exemplo.com/y",
        ))
        self.assertContains(resposta, "Informe um link válido do Instagram")
        self.assertContains(resposta, "Informe um link válido do WhatsApp")
        self.assertFalse(Aliado.objects.exists())

    def test_instagram_whatsapp_e_foto_sao_opcionais(self):
        self.client.post(reverse("web:novo-negocio"), self._dados(link_instagram="", link_whatsapp=""))
        aliado = Aliado.objects.get()
        self.assertFalse(aliado.foto)

    def test_vitrine_mostra_a_foto_do_negocio_aprovado(self):
        aliado = criar_aliado(self.lojista, foto=imagem_png())
        self.assertContains(self.client.get(reverse("web:aliados")), aliado.foto.url)

    def test_dono_edita_aprovado_com_autonomia_sem_sair_da_vitrine(self):
        aliado = criar_aliado(self.lojista, selo_verificado=True)
        resposta = self.client.get(reverse("web:editar-negocio", args=[aliado.pk]))
        self.assertNotContains(resposta, "volta para a análise")
        self.client.post(reverse("web:editar-negocio", args=[aliado.pk]),
                         self._dados(nome_negocio="Bar do Arruda", categoria="BAR", descricao="Novo cardápio."))
        aliado.refresh_from_db()
        self.assertEqual(aliado.descricao, "Novo cardápio.")
        self.assertEqual(aliado.status_aprovacao, StatusAprovacao.APROVADO)
        self.assertTrue(aliado.selo_verificado)
        self.assertContains(self.client.get(reverse("web:aliados")), "Novo cardápio.")

    def test_salvar_sem_mudar_nada_nao_tira_da_vitrine(self):
        aliado = criar_aliado(self.lojista, link_instagram="https://instagram.com/bar")
        self.client.post(reverse("web:editar-negocio", args=[aliado.pk]), {
            "nome_negocio": aliado.nome_negocio, "categoria": aliado.categoria, "descricao": aliado.descricao,
            "link_instagram": aliado.link_instagram, "link_whatsapp": "",
        })
        aliado.refresh_from_db()
        self.assertTrue(aliado.aprovado)

    def test_troca_e_remove_a_foto(self):
        aliado = criar_aliado(self.lojista, foto=imagem_png(), status_aprovacao=StatusAprovacao.PENDENTE)
        antiga, armazenamento = aliado.foto.name, aliado.foto.storage
        url = reverse("web:editar-negocio", args=[aliado.pk])
        base = {"nome_negocio": aliado.nome_negocio, "categoria": aliado.categoria, "descricao": aliado.descricao}
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(url, {**base, "foto": imagem_png("nova.png")})
        aliado.refresh_from_db()
        self.assertNotEqual(aliado.foto.name, antiga)
        self.assertFalse(armazenamento.exists(antiga))
        nova = aliado.foto.name
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(url, {**base, "foto-clear": "on"})
        aliado.refresh_from_db()
        self.assertFalse(aliado.foto)
        self.assertFalse(armazenamento.exists(nova))

    def test_exclui_o_proprio_negocio_e_o_arquivo_da_foto(self):
        aliado = criar_aliado(self.lojista, foto=imagem_png())
        arquivo, armazenamento = aliado.foto.name, aliado.foto.storage
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(reverse("web:excluir-negocio", args=[aliado.pk]))
        self.assertFalse(Aliado.objects.exists())
        self.assertFalse(armazenamento.exists(arquivo))

    def test_nao_edita_nem_exclui_negocio_de_outra_pessoa(self):
        alheio = criar_aliado()
        self.assertEqual(self.client.get(reverse("web:editar-negocio", args=[alheio.pk])).status_code, 403)
        self.assertEqual(self.client.post(reverse("web:editar-negocio", args=[alheio.pk]), self._dados()).status_code, 403)
        self.assertEqual(self.client.post(reverse("web:excluir-negocio", args=[alheio.pk])).status_code, 403)
        self.assertTrue(Aliado.objects.filter(pk=alheio.pk).exists())
        self.assertNotContains(self.client.get(reverse("web:meus-negocios")), alheio.nome_negocio)

    def test_limite_de_negocios_por_conta(self):
        for i in range(AliadoService.MAXIMO_POR_USUARIO):
            criar_aliado(self.lojista, nome_negocio=f"Negócio {i}")
        resposta = self.client.post(reverse("web:novo-negocio"), self._dados())
        self.assertContains(resposta, "Cada conta pode cadastrar até")
        self.assertFalse(Aliado.objects.filter(nome_negocio="Camisas Coral").exists())

    def test_torcedor_cadastra_e_vira_lojista_quando_aprovado(self):
        torcedor = criar_usuario()
        self.client.force_login(torcedor)
        self.client.post(reverse("web:novo-negocio"), self._dados())
        aliado = Aliado.objects.get(usuario=torcedor)
        self.client.force_login(criar_usuario(TipoUsuario.ADMIN))
        self.client.post(reverse("web:admin-moderar-negocio", args=[aliado.pk]), {"acao": "aprovar"})
        torcedor.refresh_from_db()
        aliado.refresh_from_db()
        self.assertTrue(aliado.aprovado)
        self.assertEqual(torcedor.tipo_usuario, TipoUsuario.RESPONSAVEL_ALIADO)

    def test_embaixador_que_cadastra_negocio_continua_embaixador(self):
        embaixador = criar_usuario(TipoUsuario.RESPONSAVEL_CONSULADO)
        aliado = criar_aliado(embaixador, status_aprovacao=StatusAprovacao.PENDENTE)
        AliadoService().aprovar(aliado, moderador=criar_usuario(TipoUsuario.ADMIN))
        embaixador.refresh_from_db()
        self.assertEqual(embaixador.tipo_usuario, TipoUsuario.RESPONSAVEL_CONSULADO)


# --------------------------------------------------------------- administração
class AdministracaoTests(TestCase):
    def setUp(self):
        self.admin = criar_usuario(TipoUsuario.ADMIN, nome="Gestora")
        self.client.force_login(self.admin)

    def test_telas_sao_exclusivas_de_administradores(self):
        nomes = ("web:admin-negocios", "web:admin-usuarios", "web:admin-partidas", "web:admin-nova-partida",
                 "web:solicitacoes", "web:reportes")
        for usuario in (criar_usuario(), criar_usuario(TipoUsuario.RESPONSAVEL_CONSULADO),
                        criar_usuario(TipoUsuario.RESPONSAVEL_ALIADO)):
            self.client.force_login(usuario)
            for nome in nomes:
                self.assertEqual(self.client.get(reverse(nome)).status_code, 403, nome)
        self.client.force_login(self.admin)
        for nome in nomes:
            self.assertEqual(self.client.get(reverse(nome)).status_code, 200, nome)

    def test_acoes_de_administracao_recusam_quem_nao_e_admin(self):
        alvo, aliado, partida = criar_usuario(), criar_aliado(status_aprovacao=StatusAprovacao.PENDENTE), criar_partida()
        self.client.force_login(criar_usuario(TipoUsuario.RESPONSAVEL_CONSULADO))
        chamadas = (
            ("web:admin-moderar-negocio", aliado.pk, {"acao": "aprovar"}),
            ("web:admin-papel-usuario", alvo.pk, {"tipo_usuario": "ADMIN"}),
            ("web:admin-acesso-usuario", alvo.pk, {"acao": "bloquear"}),
            ("web:admin-excluir-partida", partida.pk, {}),
            ("web:admin-editar-partida", partida.pk, {"adversario": "X"}),
        )
        for nome, pk, dados in chamadas:
            self.assertEqual(self.client.post(reverse(nome, args=[pk]), dados).status_code, 403, nome)
        alvo.refresh_from_db()
        aliado.refresh_from_db()
        self.assertEqual(alvo.tipo_usuario, TipoUsuario.TORCEDOR)
        self.assertTrue(alvo.is_active)
        self.assertEqual(aliado.status_aprovacao, StatusAprovacao.PENDENTE)
        self.assertTrue(Partida.objects.filter(pk=partida.pk).exists())

    def test_abas_mostram_as_pendencias(self):
        criar_aliado(status_aprovacao=StatusAprovacao.PENDENTE)
        criar_consulado(status_aprovacao=StatusAprovacao.PENDENTE)
        pagina = self.client.get(reverse("web:admin-usuarios"))
        self.assertEqual(pagina.context["total_negocios"], 1)
        self.assertEqual(pagina.context["total_solicitacoes"], 1)
        for nome in ("web:solicitacoes", "web:admin-negocios", "web:admin-usuarios", "web:admin-partidas", "web:reportes"):
            self.assertContains(pagina, reverse(nome))

    # negócios
    def test_recusa_negocio_com_motivo_que_o_dono_ve(self):
        dono = criar_usuario(TipoUsuario.RESPONSAVEL_ALIADO)
        aliado = criar_aliado(dono, status_aprovacao=StatusAprovacao.PENDENTE)
        self.client.post(reverse("web:admin-moderar-negocio", args=[aliado.pk]),
                         {"acao": "rejeitar", "motivo": "Link do Instagram não abre."})
        aliado.refresh_from_db()
        self.assertEqual(aliado.status_aprovacao, StatusAprovacao.REJEITADO)
        self.client.force_login(dono)
        self.assertContains(self.client.get(reverse("web:meus-negocios")), "Link do Instagram não abre.")

    def test_dono_corrige_negocio_recusado_e_ele_volta_para_analise(self):
        dono = criar_usuario(TipoUsuario.RESPONSAVEL_ALIADO)
        aliado = criar_aliado(dono, status_aprovacao=StatusAprovacao.REJEITADO, motivo_rejeicao="Sem descrição.")
        self.client.force_login(dono)
        self.client.post(reverse("web:editar-negocio", args=[aliado.pk]), {
            "nome_negocio": aliado.nome_negocio, "categoria": aliado.categoria, "descricao": "Agora com descrição completa.",
        })
        aliado.refresh_from_db()
        self.assertEqual(aliado.status_aprovacao, StatusAprovacao.PENDENTE)
        self.assertEqual(aliado.motivo_rejeicao, "")

    def test_selo_de_verificado_e_tirar_da_vitrine(self):
        aliado = criar_aliado()
        url = reverse("web:admin-moderar-negocio", args=[aliado.pk])
        self.client.post(url, {"acao": "selo"})
        aliado.refresh_from_db()
        self.assertTrue(aliado.selo_verificado)
        self.client.post(url, {"acao": "rejeitar"})
        aliado.refresh_from_db()
        self.assertEqual(aliado.status_aprovacao, StatusAprovacao.REJEITADO)
        self.assertFalse(aliado.selo_verificado)

    def test_admin_edita_negocio_de_outra_pessoa_sem_tirar_da_vitrine(self):
        aliado = criar_aliado()
        resposta = self.client.post(reverse("web:editar-negocio", args=[aliado.pk]), {
            "nome_negocio": "Bar do Arruda", "categoria": "BAR", "descricao": "Texto revisado pela administração.",
        })
        self.assertRedirects(resposta, reverse("web:admin-negocios"))
        aliado.refresh_from_db()
        self.assertTrue(aliado.aprovado)
        self.assertEqual(aliado.descricao, "Texto revisado pela administração.")

    # usuários
    def test_busca_e_filtra_usuarios(self):
        criar_usuario(nome="Juba Coral", email="juba@coral.com.br")
        criar_usuario(TipoUsuario.RESPONSAVEL_ALIADO, nome="Lia Lojista")
        pagina = self.client.get(reverse("web:admin-usuarios"), {"q": "juba"})
        self.assertContains(pagina, "Juba Coral")
        self.assertNotContains(pagina, "Lia Lojista")
        pagina = self.client.get(reverse("web:admin-usuarios"), {"papel": "RESPONSAVEL_ALIADO"})
        self.assertContains(pagina, "Lia Lojista")
        self.assertNotContains(pagina, "Juba Coral")

    def test_troca_o_papel_de_uma_conta(self):
        alvo = criar_usuario()
        self.client.post(reverse("web:admin-papel-usuario", args=[alvo.pk]), {"tipo_usuario": "RESPONSAVEL_ALIADO"})
        alvo.refresh_from_db()
        self.assertEqual(alvo.tipo_usuario, TipoUsuario.RESPONSAVEL_ALIADO)
        self.client.post(reverse("web:admin-papel-usuario", args=[alvo.pk]), {"tipo_usuario": "INVALIDO"})
        alvo.refresh_from_db()
        self.assertEqual(alvo.tipo_usuario, TipoUsuario.RESPONSAVEL_ALIADO)

    def test_bloqueia_e_libera_o_acesso(self):
        alvo = criar_usuario(email="alvo@coral.com")
        url = reverse("web:admin-acesso-usuario", args=[alvo.pk])
        self.client.post(url, {"acao": "bloquear"})
        alvo.refresh_from_db()
        self.assertFalse(alvo.is_active)
        self.client.logout()
        entrar = self.client.post(reverse("web:login"), {"username": "alvo@coral.com", "password": "SenhaForte#123"})
        self.assertEqual(entrar.status_code, 200)  # continua na tela de login
        self.client.force_login(self.admin)
        self.client.post(url, {"acao": "liberar"})
        alvo.refresh_from_db()
        self.assertTrue(alvo.is_active)

    def test_admin_nao_altera_a_propria_conta(self):
        self.client.post(reverse("web:admin-papel-usuario", args=[self.admin.pk]), {"tipo_usuario": "TORCEDOR"})
        self.client.post(reverse("web:admin-acesso-usuario", args=[self.admin.pk]), {"acao": "bloquear"})
        self.admin.refresh_from_db()
        self.assertEqual(self.admin.tipo_usuario, TipoUsuario.ADMIN)
        self.assertTrue(self.admin.is_active)

    def test_superusuario_so_e_alterado_por_superusuario(self):
        dono = criar_usuario(TipoUsuario.ADMIN, is_superuser=True, is_staff=True)
        self.client.post(reverse("web:admin-acesso-usuario", args=[dono.pk]), {"acao": "bloquear"})
        dono.refresh_from_db()
        self.assertTrue(dono.is_active)

    # partidas
    def test_cadastra_edita_e_exclui_partida(self):
        quando = (timezone.localtime() + timedelta(days=5)).strftime("%Y-%m-%dT%H:%M")
        resposta = self.client.post(reverse("web:admin-nova-partida"), {
            "adversario": "Náutico", "mando_campo": "CASA", "campeonato": "Pernambucano", "data_hora": quando,
            "canal_transmissao": "",
        })
        self.assertRedirects(resposta, reverse("web:admin-partidas"))
        partida = Partida.objects.get(adversario="Náutico")
        self.assertContains(self.client.get(reverse("web:partidas")), "Santa Cruz x Náutico")
        self.client.post(reverse("web:admin-editar-partida", args=[partida.pk]), {
            "adversario": "Sport", "mando_campo": "FORA", "campeonato": "Pernambucano", "data_hora": quando,
            "canal_transmissao": "TV Globo",
        })
        partida.refresh_from_db()
        self.assertEqual((partida.adversario, partida.mando_campo, partida.canal_transmissao), ("Sport", "FORA", "TV Globo"))
        self.client.post(reverse("web:admin-excluir-partida", args=[partida.pk]))
        self.assertFalse(Partida.objects.exists())

    def test_partida_exige_adversario_e_data(self):
        resposta = self.client.post(reverse("web:admin-nova-partida"), {"mando_campo": "CASA", "campeonato": "Copa"})
        self.assertContains(resposta, "Informe o adversário.")
        self.assertFalse(Partida.objects.exists())
