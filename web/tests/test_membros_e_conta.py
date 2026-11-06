"""Entrada de membros por solicitação, Minha conta, equipe na página pública e mapa inicial."""
from __future__ import annotations

from django.contrib.messages import get_messages
from django.test import TestCase
from django.urls import reverse

from core.models import MembroConsulado, PresencaEvento, SolicitacaoMembro, StatusAprovacao, TipoUsuario
from core.tests.factories import criar_consulado, criar_evento, criar_partida, criar_usuario


def mensagens(resposta) -> list[str]:
    return [str(m) for m in get_messages(resposta.wsgi_request)]


class EntradaComoMembroTests(TestCase):
    def setUp(self):
        self.embaixador = criar_usuario(TipoUsuario.RESPONSAVEL_CONSULADO)
        self.consulado = criar_consulado(responsavel=self.embaixador, nome="Consulado Coral Olinda")
        MembroConsulado.objects.create(usuario=self.embaixador, consulado=self.consulado)
        self.torcedor = criar_usuario(nome="Bruno Tricolor")
        self.client.force_login(self.torcedor)
        self.url_entrar = reverse("web:solicitar-entrada", args=[self.consulado.pk])

    def _pedir(self):
        self.client.force_login(self.torcedor)
        self.client.post(self.url_entrar)
        return SolicitacaoMembro.objects.get(usuario=self.torcedor, consulado=self.consulado)

    def test_pedido_fica_pendente_e_nao_duplica(self):
        pedido = self._pedir()
        self.assertEqual(pedido.status_aprovacao, StatusAprovacao.PENDENTE)
        self.assertFalse(MembroConsulado.objects.filter(usuario=self.torcedor).exists())
        resposta = self.client.post(self.url_entrar)
        self.assertIn("Você já pediu para entrar neste consulado. Aguarde a resposta do embaixador.", mensagens(resposta))
        pagina = self.client.get(reverse("web:consulado", args=[self.consulado.pk]))
        self.assertContains(pagina, "Pedido para ser membro enviado")

    def test_torcedor_cancela_o_pedido(self):
        pedido = self._pedir()
        self.client.post(reverse("web:cancelar-pedido-entrada", args=[pedido.pk]))
        self.assertFalse(SolicitacaoMembro.objects.filter(pk=pedido.pk).exists())

    def test_embaixador_aprova_e_vira_membro(self):
        pedido = self._pedir()
        self.client.force_login(self.embaixador)
        pagina = self.client.get(reverse("web:membros", args=[self.consulado.pk]))
        self.assertContains(pagina, "Bruno Tricolor")
        self.assertContains(self.client.get(reverse("web:painel")), "1 pedido para entrar")
        self.client.post(reverse("web:responder-pedido-entrada", args=[pedido.pk]), {"decisao": "aprovar"})
        pedido.refresh_from_db()
        self.assertEqual(pedido.status_aprovacao, StatusAprovacao.APROVADO)
        self.assertEqual(pedido.respondido_por, self.embaixador)
        self.assertTrue(MembroConsulado.objects.filter(usuario=self.torcedor, consulado=self.consulado).exists())

    def test_embaixador_recusa(self):
        pedido = self._pedir()
        self.client.force_login(self.embaixador)
        self.client.post(reverse("web:responder-pedido-entrada", args=[pedido.pk]), {"decisao": "recusar"})
        pedido.refresh_from_db()
        self.assertEqual(pedido.status_aprovacao, StatusAprovacao.REJEITADO)
        self.assertFalse(MembroConsulado.objects.filter(usuario=self.torcedor).exists())
        # Recusado, o torcedor pode pedir de novo.
        self.client.force_login(self.torcedor)
        self.client.post(self.url_entrar)
        self.assertEqual(SolicitacaoMembro.objects.filter(usuario=self.torcedor, status_aprovacao="PENDENTE").count(), 1)

    def test_outro_embaixador_nao_responde(self):
        pedido = self._pedir()
        self.client.force_login(criar_usuario(TipoUsuario.RESPONSAVEL_CONSULADO))
        resposta = self.client.post(reverse("web:responder-pedido-entrada", args=[pedido.pk]), {"decisao": "aprovar"})
        self.assertEqual(resposta.status_code, 403)
        self.assertFalse(MembroConsulado.objects.filter(usuario=self.torcedor).exists())

    def test_cadastro_pelo_embaixador_atende_o_pedido(self):
        pedido = self._pedir()
        self.client.force_login(self.embaixador)
        self.client.post(reverse("web:membros", args=[self.consulado.pk]), {"email": self.torcedor.email})
        pedido.refresh_from_db()
        self.assertEqual(pedido.status_aprovacao, StatusAprovacao.APROVADO)

    def test_membro_sai_do_consulado(self):
        MembroConsulado.objects.create(usuario=self.torcedor, consulado=self.consulado)
        resposta = self.client.post(reverse("web:sair-do-consulado", args=[self.consulado.pk]))
        self.assertIn("Você saiu do Consulado Coral Olinda.", mensagens(resposta))
        self.assertFalse(MembroConsulado.objects.filter(usuario=self.torcedor).exists())

    def test_embaixador_nao_sai_do_proprio_consulado(self):
        self.client.force_login(self.embaixador)
        resposta = self.client.post(reverse("web:sair-do-consulado", args=[self.consulado.pk]))
        self.assertIn("O embaixador não pode deixar o próprio consulado.", mensagens(resposta))
        self.assertTrue(MembroConsulado.objects.filter(usuario=self.embaixador).exists())

    def test_membros_mostra_outros_consulados_de_cada_membro(self):
        MembroConsulado.objects.create(usuario=self.torcedor, consulado=self.consulado)
        outro = criar_consulado(nome="Consulado Coral Caruaru")
        MembroConsulado.objects.create(usuario=self.torcedor, consulado=outro)
        self.client.force_login(self.embaixador)
        pagina = self.client.get(reverse("web:membros", args=[self.consulado.pk]))
        self.assertContains(pagina, "Também é membro de:")
        self.assertContains(pagina, "Consulado Coral Caruaru")

    def test_proximo_so_aceita_endereco_do_proprio_site(self):
        resposta = self.client.post(self.url_entrar, {"proximo": "https://site-malicioso.com/"})
        self.assertEqual(resposta.url, reverse("web:consulado", args=[self.consulado.pk]))


class MinhaContaTests(TestCase):
    def test_lista_consulados_pedidos_e_eventos(self):
        torcedor = criar_usuario()
        membro_de = criar_consulado(nome="Consulado Coral Recife")
        MembroConsulado.objects.create(usuario=torcedor, consulado=membro_de, cargo="Tesoureiro(a)")
        pedido_em = criar_consulado(nome="Consulado Coral Natal")
        SolicitacaoMembro.objects.create(usuario=torcedor, consulado=pedido_em)
        evento = criar_evento(membro_de, titulo="Resenha pré-jogo")
        PresencaEvento.objects.create(usuario=torcedor, evento=evento)

        self.client.force_login(torcedor)
        pagina = self.client.get(reverse("web:minha-conta"))
        for texto in ("Consulado Coral Recife", "Tesoureiro(a)", "Consulado Coral Natal", "Aguardando o embaixador",
                      "Resenha pré-jogo"):
            self.assertContains(pagina, texto)
        self.assertContains(pagina, reverse("web:sair-do-consulado", args=[membro_de.pk]))

    def test_link_no_menu_do_perfil(self):
        self.client.force_login(criar_usuario())
        self.assertContains(self.client.get(reverse("web:partidas")), reverse("web:minha-conta"))


class EquipeEMapaTests(TestCase):
    def test_equipe_mostra_5_e_esconde_o_restante(self):
        consulado = criar_consulado()
        for i in range(6):
            MembroConsulado.objects.create(usuario=criar_usuario(nome=f"Membro {i}"), consulado=consulado, cargo=f"Cargo {i}")
        self.client.force_login(criar_usuario())
        pagina = self.client.get(reverse("web:consulado", args=[consulado.pk]))
        self.assertEqual(len(pagina.context["equipe_visivel"]), 5)  # embaixador + 4
        self.assertEqual(len(pagina.context["equipe_oculta"]), 2)
        self.assertContains(pagina, "Ver todos (7)")

    def test_equipe_pequena_nao_tem_ver_todos(self):
        consulado = criar_consulado()
        self.client.force_login(criar_usuario())
        self.assertNotContains(self.client.get(reverse("web:consulado", args=[consulado.pk])), "Ver todos")

    def test_mapa_destaca_consulados_do_membro(self):
        torcedor = criar_usuario()
        meu = criar_consulado(nome="Consulado Coral Olinda")
        criar_consulado(nome="Consulado Coral Rio")
        MembroConsulado.objects.create(usuario=torcedor, consulado=meu)
        self.client.force_login(torcedor)
        pagina = self.client.get(reverse("web:consulados"))
        self.assertEqual([c["nome"] for c in pagina.context["meus_consulados"]], ["Consulado Coral Olinda"])
        self.assertContains(pagina, "Seu consulado")


class WhatsappObrigatorioTests(TestCase):
    def test_solicitacao_exige_whatsapp(self):
        self.client.force_login(criar_usuario())
        resposta = self.client.post(reverse("web:solicitar-consulado"), {
            "nome": "Consulado Coral Caruaru", "endereco": "Rua A, 1", "latitude": "-8.28", "longitude": "-35.97",
            "aceite_requisitos": "on", "link_whatsapp": "",
        })
        self.assertContains(resposta, "Informe o link do grupo do WhatsApp do consulado.")

    def test_edicao_exige_whatsapp(self):
        embaixador = criar_usuario(TipoUsuario.RESPONSAVEL_CONSULADO)
        consulado = criar_consulado(responsavel=embaixador, link_whatsapp="https://chat.whatsapp.com/abc")
        self.client.force_login(embaixador)
        resposta = self.client.post(reverse("web:editar-consulado", args=[consulado.pk]), {
            "endereco": "Rua Nova", "link_whatsapp": "", "descricao": "",
        })
        self.assertContains(resposta, "Informe o link do grupo do WhatsApp do consulado.")
        consulado.refresh_from_db()
        self.assertEqual(consulado.link_whatsapp, "https://chat.whatsapp.com/abc")
