"""Carona Coral: quem oferece, visibilidade só para membros, reservas, check-in e PDF."""
from __future__ import annotations

from datetime import timedelta

from django.contrib.messages import get_messages
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from core.exceptions import ConflitoError, PermissaoNegadaError, RegraNegocioError
from core.models import Carona, MembroConsulado, ReservaCarona, TipoUsuario
from core.repositories import CaronaRepository
from core.services import CaronaService
from core.tests.factories import criar_carona, criar_consulado, criar_usuario


def mensagens(resposta) -> list[str]:
    return [str(m) for m in get_messages(resposta.wsgi_request)]


def local(data) -> str:
    return timezone.localtime(data).strftime("%Y-%m-%dT%H:%M")


class Cenario(TestCase):
    """Consulado com embaixador, membro com cargo, membro comum e um torcedor de fora."""

    def setUp(self):
        self.consulado = criar_consulado()
        self.embaixador = self.consulado.responsavel
        MembroConsulado.objects.create(usuario=self.embaixador, consulado=self.consulado)
        self.diretor = criar_usuario(nome="Diretora Ana")
        MembroConsulado.objects.create(usuario=self.diretor, consulado=self.consulado, cargo="Diretor(a) de eventos")
        self.membro = criar_usuario(nome="Membro Beto")
        MembroConsulado.objects.create(usuario=self.membro, consulado=self.consulado)
        self.de_fora = criar_usuario(nome="Torcedor de Fora")
        self.servico = CaronaService()

    def dados(self, **extra):
        encontro = timezone.now() + timedelta(days=1)
        dados = {
            "descricao": "Saída da sede às 14h.", "vagas": 2,
            "data_hora_encontro": encontro, "expira_em": encontro - timedelta(hours=1),
        }
        dados.update(extra)
        return dados


class QuemOfereceTests(Cenario):
    def test_embaixador_membro_com_cargo_e_admin_oferecem(self):
        admin = criar_usuario(TipoUsuario.ADMIN)
        for usuario in (self.embaixador, self.diretor, admin):
            carona = self.servico.criar_carona(usuario, self.consulado, **self.dados())
            self.assertEqual(carona.motorista, usuario)

    def test_membro_sem_cargo_nao_oferece(self):
        with self.assertRaises(PermissaoNegadaError):
            self.servico.criar_carona(self.membro, self.consulado, **self.dados())

    def test_cargo_em_outro_consulado_nao_vale(self):
        outro = criar_consulado()
        with self.assertRaises(PermissaoNegadaError):
            self.servico.criar_carona(self.diretor, outro, **self.dados())


class ValidacaoTests(Cenario):
    def assertErro(self, campo, **extra):
        with self.assertRaises(RegraNegocioError) as erro:
            self.servico.criar_carona(self.embaixador, self.consulado, **self.dados(**extra))
        self.assertEqual(erro.exception.campo, campo)

    def test_oferta_expira_ate_o_encontro(self):
        encontro = timezone.now() + timedelta(days=1)
        self.assertErro("expira_em", data_hora_encontro=encontro, expira_em=encontro + timedelta(minutes=1))

    def test_encontro_no_passado(self):
        passado = timezone.now() - timedelta(hours=1)
        self.assertErro("data_hora_encontro", data_hora_encontro=passado, expira_em=passado - timedelta(hours=1))

    def test_texto_ate_500_caracteres(self):
        self.assertErro("descricao", descricao="x" * 501)
        carona = self.servico.criar_carona(self.embaixador, self.consulado, **self.dados(descricao="x" * 500))
        self.assertEqual(len(carona.descricao), 500)

    def test_vagas_validas(self):
        self.assertErro("vagas", vagas=0)
        self.assertErro("vagas", vagas=CaronaService.MAXIMO_VAGAS + 1)

    def test_nao_reduz_vagas_abaixo_das_reservas(self):
        carona = criar_carona(self.consulado, vagas=2)
        ReservaCarona.objects.create(carona=carona, usuario=self.membro)
        ReservaCarona.objects.create(carona=carona, usuario=self.diretor)
        with self.assertRaises(RegraNegocioError) as erro:
            self.servico.atualizar_carona(carona, self.embaixador, vagas=1)
        self.assertEqual(erro.exception.campo, "vagas")


class VisibilidadeTests(Cenario):
    def visiveis(self, usuario):
        return set(CaronaRepository().visiveis_para(usuario).values_list("pk", flat=True))

    def test_so_membros_veem(self):
        carona = criar_carona(self.consulado)
        self.assertIn(carona.pk, self.visiveis(self.membro))
        self.assertNotIn(carona.pk, self.visiveis(self.de_fora))

    def test_expirada_some_para_membros_mas_nao_para_passageiro_e_motorista(self):
        encontro = timezone.now() + timedelta(hours=3)
        carona = criar_carona(self.consulado, motorista=self.diretor, data_hora_encontro=encontro,
                              expira_em=timezone.now() - timedelta(minutes=1))
        ReservaCarona.objects.create(carona=carona, usuario=self.membro)
        outro_membro = criar_usuario()
        MembroConsulado.objects.create(usuario=outro_membro, consulado=self.consulado)
        self.assertNotIn(carona.pk, self.visiveis(outro_membro))
        self.assertIn(carona.pk, self.visiveis(self.membro))
        self.assertIn(carona.pk, self.visiveis(self.diretor))
        self.assertIn(carona.pk, self.visiveis(self.embaixador))


class ReservaTests(Cenario):
    def setUp(self):
        super().setUp()
        self.carona = criar_carona(self.consulado, motorista=self.diretor, vagas=1)

    def test_membro_reserva(self):
        reserva = self.servico.reservar(self.membro, self.carona)
        self.assertEqual(reserva.usuario, self.membro)

    def test_quem_nao_e_membro_nao_reserva(self):
        with self.assertRaises(PermissaoNegadaError):
            self.servico.reservar(self.de_fora, self.carona)

    def test_motorista_nao_reserva_na_propria_carona(self):
        with self.assertRaises(RegraNegocioError):
            self.servico.reservar(self.diretor, self.carona)

    def test_nao_reserva_duas_vezes_nem_alem_das_vagas(self):
        self.servico.reservar(self.membro, self.carona)
        with self.assertRaises(ConflitoError):
            self.servico.reservar(self.membro, self.carona)
        with self.assertRaises(RegraNegocioError) as erro:
            self.servico.reservar(self.embaixador, self.carona)
        self.assertEqual(erro.exception.codigo, "esgotado")

    def test_nao_reserva_oferta_expirada(self):
        Carona.objects.filter(pk=self.carona.pk).update(expira_em=timezone.now() - timedelta(minutes=1))
        with self.assertRaises(RegraNegocioError):
            self.servico.reservar(self.membro, self.carona)

    def test_nao_cancela_depois_do_encontro(self):
        reserva = self.servico.reservar(self.membro, self.carona)
        agora = timezone.now()
        Carona.objects.filter(pk=self.carona.pk).update(
            data_hora_encontro=agora - timedelta(minutes=5), expira_em=agora - timedelta(minutes=10),
        )
        reserva.refresh_from_db()
        with self.assertRaises(RegraNegocioError):
            self.servico.cancelar_reserva(self.membro, reserva)


class CheckinTests(Cenario):
    def setUp(self):
        super().setUp()
        self.carona = criar_carona(self.consulado, motorista=self.diretor)
        self.reserva = ReservaCarona.objects.create(carona=self.carona, usuario=self.membro)

    def test_motorista_faz_e_desfaz_checkin(self):
        self.servico.registrar_checkin(self.diretor, self.reserva)
        self.reserva.refresh_from_db()
        self.assertIsNotNone(self.reserva.checkin_em)
        self.assertEqual(self.reserva.checkin_por, self.diretor)
        with self.assertRaises(ConflitoError):
            self.servico.registrar_checkin(self.diretor, self.reserva)
        self.servico.desfazer_checkin(self.diretor, self.reserva)
        self.reserva.refresh_from_db()
        self.assertIsNone(self.reserva.checkin_em)

    def test_embaixador_tambem_faz_checkin(self):
        self.servico.registrar_checkin(self.embaixador, self.reserva)

    def test_passageiro_nao_faz_checkin(self):
        with self.assertRaises(PermissaoNegadaError):
            self.servico.registrar_checkin(self.membro, self.reserva)


class PaginasTests(Cenario):
    def test_painel_mostra_carona_coral_para_membro_com_cargo(self):
        criar_carona(self.consulado, motorista=self.diretor)
        self.client.force_login(self.diretor)
        pagina = self.client.get(reverse("web:painel"))
        self.assertContains(pagina, "Carona Coral")
        self.assertContains(pagina, reverse("web:nova-carona", args=[self.consulado.pk]))
        self.assertContains(pagina, "Carona de Diretora Ana")

    def test_oferecer_pelo_formulario(self):
        self.client.force_login(self.diretor)
        encontro = timezone.now() + timedelta(days=3)
        resposta = self.client.post(reverse("web:nova-carona", args=[self.consulado.pk]), {
            "descricao": "Saída da sede.", "vagas": "4",
            "data_hora_encontro": local(encontro), "expira_em": local(encontro - timedelta(hours=2)),
        })
        self.assertRedirects(resposta, f"{reverse('web:painel')}?consulado={self.consulado.pk}")
        self.assertTrue(Carona.objects.filter(motorista=self.diretor, vagas=4).exists())

    def test_formulario_mostra_erro_do_prazo(self):
        self.client.force_login(self.diretor)
        encontro = timezone.now() + timedelta(days=3)
        resposta = self.client.post(reverse("web:nova-carona", args=[self.consulado.pk]), {
            "descricao": "Saída da sede.", "vagas": "4",
            "data_hora_encontro": local(encontro), "expira_em": local(encontro + timedelta(hours=1)),
        })
        self.assertContains(resposta, "A oferta precisa expirar até o horário do encontro.")
        self.assertFalse(Carona.objects.exists())

    def test_membro_sem_cargo_nao_abre_o_formulario(self):
        self.client.force_login(self.membro)
        resposta = self.client.get(reverse("web:nova-carona", args=[self.consulado.pk]))
        self.assertEqual(resposta.status_code, 403)

    def test_membro_ve_e_reserva_na_pagina_do_consulado(self):
        carona = criar_carona(self.consulado, motorista=self.diretor)
        self.client.force_login(self.membro)
        url = reverse("web:consulado", args=[self.consulado.pk])
        self.assertContains(self.client.get(url), "Reservar vaga")
        resposta = self.client.post(reverse("web:reservar-carona", args=[carona.pk]), {"proximo": url})
        self.assertRedirects(resposta, url)
        self.assertIn("Vaga reservada na carona de Diretora Ana.", mensagens(resposta))
        self.assertContains(self.client.get(url), "Cancelar reserva")
        self.assertContains(self.client.get(reverse("web:minha-conta")), "Carona de Diretora Ana")

    def test_quem_nao_e_membro_nao_ve_as_caronas(self):
        carona = criar_carona(self.consulado, motorista=self.diretor)
        self.client.force_login(self.de_fora)
        pagina = self.client.get(reverse("web:consulado", args=[self.consulado.pk]))
        self.assertNotContains(pagina, "Carona Coral")
        resposta = self.client.post(reverse("web:reservar-carona", args=[carona.pk]))
        self.assertEqual(resposta.status_code, 404)

    def test_lista_de_passageiros_checkin_e_pdf(self):
        carona = criar_carona(self.consulado, motorista=self.diretor)
        reserva = ReservaCarona.objects.create(carona=carona, usuario=self.membro)
        self.client.force_login(self.diretor)
        pagina = self.client.get(reverse("web:passageiros-carona", args=[carona.pk]))
        self.assertContains(pagina, "Membro Beto")
        self.client.post(reverse("web:checkin-carona", args=[reserva.pk]))
        reserva.refresh_from_db()
        self.assertIsNotNone(reserva.checkin_em)
        pdf = self.client.get(reverse("web:passageiros-carona-pdf", args=[carona.pk]))
        self.assertEqual(pdf["Content-Type"], "application/pdf")
        self.assertTrue(pdf.content.startswith(b"%PDF"))

    def test_retirado_nao_reserva_de_novo_ate_ser_readmitido(self):
        carona = criar_carona(self.consulado, motorista=self.diretor, vagas=1)
        reserva = ReservaCarona.objects.create(carona=carona, usuario=self.membro)
        self.client.force_login(self.diretor)
        resposta = self.client.post(reverse("web:retirar-passageiro", args=[reserva.pk]))
        self.assertIn("Membro Beto foi retirado(a) da carona e a vaga ficou livre.", mensagens(resposta))
        self.assertFalse(ReservaCarona.objects.filter(pk=reserva.pk).exists())  # sai das listas e contagens
        self.assertTrue(ReservaCarona.todas.filter(pk=reserva.pk, removida_em__isnull=False).exists())
        self.assertContains(self.client.get(reverse("web:passageiros-carona", args=[carona.pk])), "Readmitir")

        self.client.force_login(self.membro)
        pagina = self.client.get(reverse("web:consulado", args=[self.consulado.pk]))
        self.assertContains(pagina, "Sua reserva foi retirada por quem oferece a carona")
        resposta = self.client.post(reverse("web:reservar-carona", args=[carona.pk]))
        self.assertIn("Quem oferece esta carona retirou a sua reserva.", mensagens(resposta))

        # A vaga liberada pode ir para outra pessoa; com ela ocupada, ninguém é readmitido.
        CaronaService().reservar(self.embaixador, carona)
        self.client.force_login(self.diretor)
        resposta = self.client.post(reverse("web:readmitir-passageiro", args=[reserva.pk]))
        self.assertIn("Todas as vagas estão ocupadas: libere uma antes de readmitir alguém.", mensagens(resposta))

        ReservaCarona.objects.filter(usuario=self.embaixador).delete()
        resposta = self.client.post(reverse("web:readmitir-passageiro", args=[reserva.pk]))
        self.assertIn("Membro Beto voltou para a carona.", mensagens(resposta))
        self.assertTrue(ReservaCarona.objects.filter(pk=reserva.pk).exists())

    def test_nao_retira_passageiro_com_checkin(self):
        carona = criar_carona(self.consulado, motorista=self.diretor)
        reserva = ReservaCarona.objects.create(carona=carona, usuario=self.membro, checkin_em=timezone.now())
        with self.assertRaises(RegraNegocioError):
            CaronaService().retirar_passageiro(self.diretor, reserva)

    def test_contagem_de_vagas_ignora_retirados(self):
        carona = criar_carona(self.consulado, motorista=self.diretor)
        ReservaCarona.objects.create(carona=carona, usuario=self.membro, removida_em=timezone.now())
        anotada = CaronaRepository().visiveis_para(self.diretor).get(pk=carona.pk)
        self.assertEqual(anotada.total_reservas, 0)

    def test_pdf_aceita_caracteres_especiais(self):
        consulado = criar_consulado(nome="Consulado <b>Coral & Cia")
        carona = criar_carona(consulado, descricao="Saída <b>15h & volta")
        ReservaCarona.objects.create(carona=carona, usuario=criar_usuario(nome="Ana <b>Silva & Filhos"))
        self.client.force_login(consulado.responsavel)
        pdf = self.client.get(reverse("web:passageiros-carona-pdf", args=[carona.pk]))
        self.assertTrue(pdf.content.startswith(b"%PDF"))

    def test_passageiro_nao_ve_a_lista(self):
        carona = criar_carona(self.consulado, motorista=self.diretor)
        ReservaCarona.objects.create(carona=carona, usuario=self.membro)
        self.client.force_login(self.membro)
        self.assertEqual(self.client.get(reverse("web:passageiros-carona", args=[carona.pk])).status_code, 403)
        self.assertEqual(self.client.get(reverse("web:passageiros-carona-pdf", args=[carona.pk])).status_code, 403)
