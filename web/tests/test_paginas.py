"""Testes das páginas da interface web (login por sessão + mesmas regras da API)."""
from __future__ import annotations

from datetime import timedelta

from django.contrib.messages import get_messages
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from core.models import (
    Aliado, CategoriaAliado, Consulado, Evento, MembroConsulado, PresencaEvento, StatusAprovacao,
    TipoUsuario, Usuario,
)
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


class PresencaTests(TestCase):
    def setUp(self):
        self.torcedor = criar_usuario()
        self.consulado = criar_consulado()
        self.evento = criar_evento(self.consulado)
        self.client.force_login(self.torcedor)
        self.url = reverse("web:confirmar-presenca", args=[self.evento.pk])

    def test_nao_membro_confirma_evento_livre(self):
        resposta = self.client.post(self.url)
        self.assertTrue(PresencaEvento.objects.filter(usuario=self.torcedor, evento=self.evento).exists())
        self.assertIn(f'Presença confirmada em "{self.evento.titulo}".', mensagens(resposta))

    def test_evento_exclusivo_some_para_nao_membro(self):
        exclusivo = criar_evento(self.consulado, titulo="Churrasco dos sócios", exclusivo_membros=True)
        pagina = self.client.get(reverse("web:consulado", args=[self.consulado.pk]))
        self.assertContains(pagina, self.evento.titulo)
        self.assertNotContains(pagina, "Churrasco dos sócios")
        # Nem pela URL direta dá para confirmar presença.
        resposta = self.client.post(reverse("web:confirmar-presenca", args=[exclusivo.pk]))
        self.assertEqual(resposta.status_code, 404)

    def test_membro_ve_e_confirma_evento_exclusivo(self):
        MembroConsulado.objects.create(usuario=self.torcedor, consulado=self.consulado)
        exclusivo = criar_evento(self.consulado, titulo="Churrasco dos sócios", exclusivo_membros=True)
        pagina = self.client.get(reverse("web:consulado", args=[self.consulado.pk]))
        self.assertContains(pagina, "Churrasco dos sócios")
        self.client.post(reverse("web:confirmar-presenca", args=[exclusivo.pk]))
        self.assertTrue(PresencaEvento.objects.filter(usuario=self.torcedor, evento=exclusivo).exists())

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

    def test_painel_mostra_presencas_e_membros(self):
        evento = criar_evento(self.consulado)
        PresencaEvento.objects.create(usuario=criar_usuario(nome="Maria Coral"), evento=evento)
        MembroConsulado.objects.create(usuario=criar_usuario(), consulado=self.consulado)
        resposta = self.client.get(reverse("web:painel"))
        self.assertContains(resposta, "Consulado CoralJampa")
        self.assertContains(resposta, "Presenças em eventos")
        self.assertContains(resposta, "Membros do consulado")
        self.assertNotContains(resposta, "Check-ins no próximo jogo")
        self.assertEqual(resposta.context["presencas_previstas"], 1)
        self.assertEqual(resposta.context["consulado"].total_membros, 1)

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

    def test_novo_evento_ja_nasce_publicado(self):
        inicio = timezone.localtime() + timedelta(days=2)
        resposta = self.client.post(reverse("web:novo-evento", args=[self.consulado.pk]), {
            "titulo": "Resenha pré-jogo",
            "descricao": "",
            "inicio": inicio.strftime("%Y-%m-%dT%H:%M"),
            "duracao": "3",
        })
        self.assertEqual(resposta.status_code, 302)
        evento = Evento.objects.get(titulo="Resenha pré-jogo")
        self.assertEqual(evento.status_aprovacao, StatusAprovacao.APROVADO)
        self.assertEqual(evento.data_hora_fim - evento.data_hora_inicio, timedelta(hours=3))

    def test_evento_no_passado_e_recusado(self):
        inicio = timezone.localtime() - timedelta(days=1)
        resposta = self.client.post(reverse("web:novo-evento", args=[self.consulado.pk]), {
            "titulo": "Atrasado", "inicio": inicio.strftime("%Y-%m-%dT%H:%M"), "duracao": "3",
        })
        self.assertContains(resposta, "O evento não pode começar no passado.")
        self.assertFalse(Evento.objects.exists())

    def test_editar_evento(self):
        evento = criar_evento(self.consulado, titulo="Resenha")
        url = reverse("web:editar-evento", args=[evento.pk])
        self.assertContains(self.client.get(url), 'value="Resenha"')
        inicio = timezone.localtime(evento.data_hora_inicio)
        resposta = self.client.post(url, {
            "titulo": "Resenha pré-jogo", "descricao": "Telão e petiscos",
            "inicio": inicio.strftime("%Y-%m-%dT%H:%M"), "duracao": "4", "exclusivo_membros": "on",
        })
        self.assertEqual(resposta.status_code, 302)
        evento.refresh_from_db()
        self.assertEqual(evento.titulo, "Resenha pré-jogo")
        self.assertTrue(evento.exclusivo_membros)
        self.assertEqual(evento.data_hora_fim - evento.data_hora_inicio, timedelta(hours=4))
        self.assertEqual(evento.status_aprovacao, StatusAprovacao.APROVADO)

    def test_excluir_evento(self):
        evento = criar_evento(self.consulado)
        self.client.post(reverse("web:excluir-evento", args=[evento.pk]))
        self.assertFalse(Evento.objects.filter(pk=evento.pk).exists())

    def test_nao_edita_evento_de_outro_consulado(self):
        evento = criar_evento(criar_consulado())
        self.assertEqual(self.client.get(reverse("web:editar-evento", args=[evento.pk])).status_code, 403)
        self.assertEqual(self.client.post(reverse("web:excluir-evento", args=[evento.pk])).status_code, 403)


class MembrosTests(TestCase):
    def setUp(self):
        self.embaixador = criar_usuario(TipoUsuario.RESPONSAVEL_CONSULADO, nome="Rubens")
        self.consulado = criar_consulado(responsavel=self.embaixador)
        MembroConsulado.objects.create(usuario=self.embaixador, consulado=self.consulado)
        self.client.force_login(self.embaixador)
        self.url = reverse("web:membros", args=[self.consulado.pk])

    def test_cadastra_usuario_existente_com_cargo(self):
        torcedora = criar_usuario(email="ana@coral.com", nome="Ana")
        resposta = self.client.post(self.url, {"email": "ANA@coral.com", "cargo": "Tesoureira"})
        self.assertRedirects(resposta, self.url, fetch_redirect_response=False)
        membro = MembroConsulado.objects.get(usuario=torcedora, consulado=self.consulado)
        self.assertEqual(membro.cargo, "Tesoureira")

    def test_cadastra_novo_torcedor_e_mostra_senha_provisoria_uma_vez(self):
        self.client.post(self.url, {"email": "novo@coral.com", "nome": "Novo Torcedor"})
        novo = Usuario.objects.get(email="novo@coral.com")
        self.assertEqual(novo.tipo_usuario, TipoUsuario.TORCEDOR)
        self.assertTrue(MembroConsulado.objects.filter(usuario=novo, consulado=self.consulado).exists())
        pagina = self.client.get(self.url)
        senha = pagina.context["nova_conta"]["senha"]
        self.assertTrue(novo.check_password(senha))
        self.assertContains(pagina, senha)
        self.assertNotContains(self.client.get(self.url), senha)

    def test_novo_torcedor_exige_nome(self):
        resposta = self.client.post(self.url, {"email": "novo@coral.com"})
        self.assertContains(resposta, "Informe o nome para cadastrar um novo torcedor.")
        self.assertFalse(Usuario.objects.filter(email="novo@coral.com").exists())

    def test_membro_repetido_e_recusado(self):
        torcedora = criar_usuario(nome="Ana")
        MembroConsulado.objects.create(usuario=torcedora, consulado=self.consulado)
        resposta = self.client.post(self.url, {"email": torcedora.email})
        self.assertContains(resposta, "Ana já é membro deste consulado.")

    def test_cargo_aparece_na_pagina_publica(self):
        membro = MembroConsulado.objects.create(usuario=criar_usuario(nome="Ana Coral"), consulado=self.consulado)
        self.client.post(reverse("web:definir-cargo", args=[membro.pk]), {"cargo": "Vice-presidente"})
        self.client.force_login(criar_usuario())
        pagina = self.client.get(reverse("web:consulado", args=[self.consulado.pk]))
        self.assertContains(pagina, "Equipe do consulado")
        self.assertContains(pagina, "Ana Coral")
        self.assertContains(pagina, "Vice-presidente")

    def test_remove_membro_mas_nao_o_embaixador(self):
        membro = MembroConsulado.objects.create(usuario=criar_usuario(), consulado=self.consulado)
        self.client.post(reverse("web:remover-membro", args=[membro.pk]))
        self.assertFalse(MembroConsulado.objects.filter(pk=membro.pk).exists())
        proprio = MembroConsulado.objects.get(usuario=self.embaixador, consulado=self.consulado)
        resposta = self.client.post(reverse("web:remover-membro", args=[proprio.pk]))
        self.assertIn("O embaixador não pode ser removido do próprio consulado.", mensagens(resposta))
        self.assertTrue(MembroConsulado.objects.filter(pk=proprio.pk).exists())

    def test_outro_embaixador_nao_gerencia(self):
        self.client.force_login(criar_usuario(TipoUsuario.RESPONSAVEL_CONSULADO))
        membro = MembroConsulado.objects.get(usuario=self.embaixador)
        self.assertEqual(self.client.get(self.url).status_code, 403)
        resposta = self.client.post(reverse("web:definir-cargo", args=[membro.pk]), {"cargo": "X"})
        self.assertEqual(resposta.status_code, 403)


class SolicitacoesTests(TestCase):
    def setUp(self):
        self.torcedor = criar_usuario(nome="Carlos")
        self.admin = criar_usuario(TipoUsuario.ADMIN)
        self.dados = {
            "nome": "Consulado Coral Caruaru", "endereco": "Rua da Matriz, 10 - Caruaru, PE",
            "latitude": "-8.283300", "longitude": "-35.975900", "link_whatsapp": "https://chat.whatsapp.com/caruaru",
            "descricao": "",
            "aceite_requisitos": "on",
        }

    def _solicitar(self, **extra):
        self.client.force_login(self.torcedor)
        return self.client.post(reverse("web:solicitar-consulado"), {**self.dados, **extra})

    def test_torcedor_ve_requisitos_e_link(self):
        self.client.force_login(self.torcedor)
        self.assertContains(self.client.get(reverse("web:consulados")), reverse("web:solicitar-consulado"))
        self.assertContains(self.client.get(reverse("web:solicitar-consulado")), "Requisitos do Santa Cruz")

    def test_solicitacao_exige_aceite_e_local(self):
        resposta = self._solicitar(aceite_requisitos="", latitude="", longitude="")
        self.assertContains(resposta, "É preciso atender aos requisitos do clube")
        self.assertContains(resposta, "Marque a localização do consulado no mapa.")
        self.assertFalse(Consulado.objects.filter(nome=self.dados["nome"]).exists())

    def test_solicitacao_nasce_pendente_e_so_uma_por_vez(self):
        self._solicitar()
        consulado = Consulado.objects.get(nome=self.dados["nome"])
        self.assertEqual(consulado.status_aprovacao, StatusAprovacao.PENDENTE)
        self.assertEqual(consulado.responsavel, self.torcedor)
        resposta = self._solicitar(nome="Consulado Coral Gravatá")
        self.assertContains(resposta, "Você já tem uma solicitação de consulado em análise.")

    def test_admin_aprova_e_torcedor_vira_embaixador(self):
        self._solicitar()
        consulado = Consulado.objects.get(nome=self.dados["nome"])
        self.client.force_login(self.admin)
        pagina = self.client.get(reverse("web:solicitacoes"))
        self.assertContains(pagina, "Consulado Coral Caruaru")
        self.assertContains(pagina, "Carlos")
        self.client.post(reverse("web:aprovar-solicitacao", args=[consulado.pk]))
        consulado.refresh_from_db()
        self.torcedor.refresh_from_db()
        self.assertEqual(consulado.status_aprovacao, StatusAprovacao.APROVADO)
        self.assertEqual(self.torcedor.tipo_usuario, TipoUsuario.RESPONSAVEL_CONSULADO)
        # O novo embaixador já acessa o painel do consulado.
        self.client.force_login(self.torcedor)
        self.assertContains(self.client.get(reverse("web:painel")), "Consulado Coral Caruaru")

    def test_admin_recusa_com_motivo(self):
        self._solicitar()
        consulado = Consulado.objects.get(nome=self.dados["nome"])
        self.client.force_login(self.admin)
        self.client.post(reverse("web:rejeitar-solicitacao", args=[consulado.pk]), {"motivo": "Endereço não confere."})
        consulado.refresh_from_db()
        self.assertEqual(consulado.status_aprovacao, StatusAprovacao.REJEITADO)
        self.torcedor.refresh_from_db()
        self.assertEqual(self.torcedor.tipo_usuario, TipoUsuario.TORCEDOR)
        # O torcedor vê o motivo e pode enviar uma nova solicitação.
        self.client.force_login(self.torcedor)
        self.assertContains(self.client.get(reverse("web:solicitar-consulado")), "Endereço não confere.")
        self._solicitar(nome="Consulado Coral Caruaru 2")
        self.assertTrue(Consulado.objects.filter(nome="Consulado Coral Caruaru 2").exists())

    def test_somente_admin_ve_e_decide_solicitacoes(self):
        self._solicitar()
        consulado = Consulado.objects.get(nome=self.dados["nome"])
        for usuario in (self.torcedor, criar_usuario(TipoUsuario.RESPONSAVEL_CONSULADO)):
            self.client.force_login(usuario)
            self.assertEqual(self.client.get(reverse("web:solicitacoes")).status_code, 403)
            aprovar = self.client.post(reverse("web:aprovar-solicitacao", args=[consulado.pk]))
            self.assertEqual(aprovar.status_code, 403)

    def test_cadastro_pelo_admin_ja_nasce_aprovado(self):
        self.client.force_login(self.admin)
        self.client.post(reverse("web:solicitar-consulado"), self.dados)
        self.assertEqual(Consulado.objects.get(nome=self.dados["nome"]).status_aprovacao, StatusAprovacao.APROVADO)
