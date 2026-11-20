"""Embaixador que era torcedor aceita pedidos de entrada no próprio consulado."""
from django.contrib.staticfiles import finders
from django.test import TestCase
from django.urls import reverse

from core.models import MembroConsulado, SolicitacaoMembro, StatusAprovacao
from core.tests.factories import criar_consulado, criar_usuario


class AceiteDeMembroTests(TestCase):
    def setUp(self):
        # Consulado aprovado direto no banco (como no Django Admin): o dono continua TORCEDOR.
        self.dono = criar_usuario()
        self.consulado = criar_consulado(responsavel=self.dono, status_aprovacao=StatusAprovacao.APROVADO)
        MembroConsulado.objects.create(usuario=self.dono, consulado=self.consulado)
        self.novo = criar_usuario()
        self.pedido = SolicitacaoMembro.objects.create(usuario=self.novo, consulado=self.consulado)
        self.client.force_login(self.dono)

    def test_dono_torcedor_tem_painel_e_aprova_o_pedido(self):
        self.assertEqual(self.client.get(reverse("web:painel")).status_code, 200)
        self.client.post(reverse("web:responder-pedido-entrada", args=[self.pedido.pk]), {"decisao": "aprovar"})
        self.assertTrue(MembroConsulado.objects.filter(usuario=self.novo, consulado=self.consulado).exists())

    def test_script_preserva_o_botao_clicado_ao_bloquear_envio_duplo(self):
        # Sem o campo oculto, o botão desativado não envia "decisao" e o pedido vira recusa.
        with open(finders.find("web/coral.js"), encoding="utf-8") as arquivo:
            js = arquivo.read()
        self.assertIn("e.submitter", js)
        self.assertIn("data-botao-enviado", js)
