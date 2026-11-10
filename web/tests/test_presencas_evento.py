"""Limite de vagas, desmarcar presença e lista de confirmados (retirar, readmitir, PDF)."""
from __future__ import annotations

from datetime import timedelta

from django.contrib.messages import get_messages
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from core.models import Evento, MembroConsulado, PresencaEvento, TipoUsuario
from core.tests.factories import criar_consulado, criar_evento, criar_partida, criar_usuario


def mensagens(resposta) -> list[str]:
    return [str(m) for m in get_messages(resposta.wsgi_request)]


class LimiteDeVagasTests(TestCase):
    def setUp(self):
        self.consulado = criar_consulado()
        self.evento = criar_evento(self.consulado, titulo="Churrasco", limite_vagas=2)
        self.url = reverse("web:confirmar-presenca", args=[self.evento.pk])

    def _confirmar(self, usuario):
        self.client.force_login(usuario)
        return self.client.post(self.url)

    def test_recusa_quando_as_vagas_acabam(self):
        self._confirmar(criar_usuario())
        self._confirmar(criar_usuario())
        terceiro = criar_usuario()
        resposta = self._confirmar(terceiro)
        self.assertIn("As vagas deste evento já foram preenchidas.", mensagens(resposta))
        self.assertEqual(PresencaEvento.objects.filter(evento=self.evento).count(), 2)
        pagina = self.client.get(reverse("web:consulado", args=[self.consulado.pk]))
        self.assertContains(pagina, "2 de 2 vagas")
        self.assertContains(pagina, "Vagas esgotadas")

    def test_limite_nao_pode_ficar_abaixo_dos_confirmados(self):
        for _ in range(2):
            PresencaEvento.objects.create(usuario=criar_usuario(), evento=self.evento)
        self.client.force_login(self.consulado.responsavel)
        inicio = timezone.localtime(self.evento.data_hora_inicio)
        resposta = self.client.post(reverse("web:editar-evento", args=[self.evento.pk]), {
            "titulo": "Churrasco", "inicio": inicio.strftime("%Y-%m-%dT%H:%M"), "duracao": "3", "limite_vagas": "1",
        })
        self.assertContains(resposta, "o limite não pode ser menor que isso")
        self.evento.refresh_from_db()
        self.assertEqual(self.evento.limite_vagas, 2)

    def test_sem_limite_por_padrao(self):
        evento = criar_evento(self.consulado)
        self.assertIsNone(evento.limite_vagas)
        for _ in range(3):
            self.client.force_login(criar_usuario())
            self.client.post(reverse("web:confirmar-presenca", args=[evento.pk]))
        self.assertEqual(PresencaEvento.objects.filter(evento=evento).count(), 3)


class DesmarcarPresencaTests(TestCase):
    def setUp(self):
        self.consulado = criar_consulado()
        self.torcedor = criar_usuario()
        self.client.force_login(self.torcedor)

    def test_botao_aparece_e_desmarca(self):
        evento = criar_evento(self.consulado, titulo="Resenha")
        PresencaEvento.objects.create(usuario=self.torcedor, evento=evento)
        pagina = self.client.get(reverse("web:consulado", args=[self.consulado.pk]))
        self.assertContains(pagina, "Desmarcar presença")
        self.assertContains(self.client.get(reverse("web:minha-conta")), "Desmarcar presença")
        resposta = self.client.post(reverse("web:desmarcar-presenca", args=[evento.pk]))
        self.assertIn('Presença em "Resenha" desmarcada.', mensagens(resposta))
        self.assertFalse(PresencaEvento.objects.filter(usuario=self.torcedor).exists())

    def test_nao_desmarca_depois_do_inicio(self):
        inicio = timezone.now() - timedelta(minutes=30)
        evento = criar_evento(self.consulado, data_hora_inicio=inicio, data_hora_fim=inicio + timedelta(hours=3))
        PresencaEvento.objects.create(usuario=self.torcedor, evento=evento)
        self.assertNotContains(self.client.get(reverse("web:consulado", args=[self.consulado.pk])), "Desmarcar presença")
        resposta = self.client.post(reverse("web:desmarcar-presenca", args=[evento.pk]))
        self.assertIn("Não é possível cancelar a presença após o início do evento.", mensagens(resposta))
        self.assertTrue(PresencaEvento.objects.filter(usuario=self.torcedor).exists())


class ListaDeConfirmadosTests(TestCase):
    def setUp(self):
        self.embaixador = criar_usuario(TipoUsuario.RESPONSAVEL_CONSULADO)
        self.consulado = criar_consulado(responsavel=self.embaixador)
        self.evento = criar_evento(self.consulado, titulo="Resenha pré-jogo", limite_vagas=1)
        self.indesejado = criar_usuario(nome="Fulano Indesejado")
        self.presenca = PresencaEvento.objects.create(usuario=self.indesejado, evento=self.evento)
        self.url = reverse("web:presencas-evento", args=[self.evento.pk])

    def test_quem_ve_a_lista(self):
        diretor = criar_usuario()
        MembroConsulado.objects.create(usuario=diretor, consulado=self.consulado, cargo="Tesoureiro(a)")
        sem_cargo = criar_usuario()
        MembroConsulado.objects.create(usuario=sem_cargo, consulado=self.consulado)
        for usuario, esperado in ((self.embaixador, 200), (diretor, 200), (criar_usuario(TipoUsuario.ADMIN), 200),
                                  (sem_cargo, 403), (criar_usuario(), 403)):
            self.client.force_login(usuario)
            self.assertEqual(self.client.get(self.url).status_code, esperado, usuario)
        self.client.force_login(self.embaixador)
        self.assertContains(self.client.get(self.url), "Fulano Indesejado")

    def test_retirado_nao_confirma_de_novo_e_pode_ser_readmitido(self):
        self.client.force_login(self.embaixador)
        self.client.post(reverse("web:remover-presenca", args=[self.presenca.pk]))
        self.assertFalse(PresencaEvento.objects.filter(pk=self.presenca.pk).exists())  # some das listas
        self.assertTrue(PresencaEvento.todas.filter(pk=self.presenca.pk, removida_por=self.embaixador).exists())
        self.assertContains(self.client.get(self.url), "Retirados da lista")

        # A vaga liberada fica disponível para outra pessoa...
        outro = criar_usuario()
        self.client.force_login(outro)
        self.client.post(reverse("web:confirmar-presenca", args=[self.evento.pk]))
        self.assertTrue(PresencaEvento.objects.filter(usuario=outro, evento=self.evento).exists())

        # ...e o retirado não consegue voltar sozinho.
        self.client.force_login(self.indesejado)
        pagina = self.client.get(reverse("web:consulado", args=[self.consulado.pk]))
        self.assertContains(pagina, "Sua presença foi retirada pela organização")
        resposta = self.client.post(reverse("web:confirmar-presenca", args=[self.evento.pk]))
        self.assertIn("A organização do consulado retirou a sua presença deste evento.", mensagens(resposta))

        # Readmitir respeita o limite de vagas (a única vaga já foi ocupada).
        self.client.force_login(self.embaixador)
        resposta = self.client.post(reverse("web:readmitir-presenca", args=[self.presenca.pk]))
        self.assertIn("Todas as vagas estão preenchidas: libere uma antes de readmitir alguém.", mensagens(resposta))
        Evento.objects.filter(pk=self.evento.pk).update(limite_vagas=None)
        self.client.post(reverse("web:readmitir-presenca", args=[self.presenca.pk]))
        self.assertTrue(PresencaEvento.objects.filter(pk=self.presenca.pk).exists())

    def test_contagem_ignora_retirados(self):
        PresencaEvento.objects.filter(pk=self.presenca.pk).update(removida_em=timezone.now())
        self.client.force_login(self.embaixador)
        painel = self.client.get(reverse("web:painel"))
        evento = next(e for e in painel.context["eventos"] if e.pk == self.evento.pk)
        self.assertEqual(evento.total_confirmados, 0)

    def test_membro_sem_cargo_nao_retira(self):
        sem_cargo = criar_usuario()
        MembroConsulado.objects.create(usuario=sem_cargo, consulado=self.consulado)
        self.client.force_login(sem_cargo)
        self.assertEqual(self.client.post(reverse("web:remover-presenca", args=[self.presenca.pk])).status_code, 403)
        self.assertTrue(PresencaEvento.objects.filter(pk=self.presenca.pk).exists())

    def test_exporta_pdf(self):
        self.client.force_login(self.embaixador)
        resposta = self.client.get(reverse("web:presencas-evento-pdf", args=[self.evento.pk]))
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta["Content-Type"], "application/pdf")
        self.assertIn('filename="lista-de-presenca-resenha-pre-jogo-', resposta["Content-Disposition"])
        self.assertTrue(resposta.content.startswith(b"%PDF"))

    def test_pdf_aceita_caracteres_especiais(self):
        # Sem escapar, o ReportLab lê "<b>" como marcação: o PDF quebra (erro 500) ou o texto some.
        Evento.objects.filter(pk=self.evento.pk).update(titulo="Resenha <b>pré-jogo & churrasco")
        PresencaEvento.objects.create(usuario=criar_usuario(nome="Ana <b>Silva & Filhos"), evento=self.evento)
        self.client.force_login(self.embaixador)
        resposta = self.client.get(reverse("web:presencas-evento-pdf", args=[self.evento.pk]))
        self.assertEqual(resposta.status_code, 200)
        self.assertTrue(resposta.content.startswith(b"%PDF"))

    def test_pdf_exige_permissao(self):
        self.client.force_login(criar_usuario())
        self.assertEqual(self.client.get(reverse("web:presencas-evento-pdf", args=[self.evento.pk])).status_code, 403)

    def test_membro_com_cargo_ve_eventos_no_painel(self):
        diretor = criar_usuario()
        MembroConsulado.objects.create(usuario=diretor, consulado=self.consulado, cargo="Secretário(a)")
        self.client.force_login(diretor)
        self.assertContains(self.client.get(reverse("web:painel")), self.url)


class ContadorDoJogoTests(TestCase):
    def test_card_do_jogo_nao_tem_checkin(self):
        consulado = criar_consulado()
        criar_partida()
        self.client.force_login(criar_usuario())
        pagina = self.client.get(reverse("web:consulado", args=[consulado.pk]))
        self.assertContains(pagina, "Próximo jogo do Santa Cruz")
        self.assertNotContains(pagina, "confirmado aqui")
        self.assertNotContains(pagina, "confirmados aqui")
        self.assertNotContains(pagina, "check-in")
