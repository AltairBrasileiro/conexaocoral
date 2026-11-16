"""Cadastro de usuário na tela inicial."""
from django.test import TestCase
from django.urls import reverse

from core.models import TipoUsuario, Usuario
from core.tests.factories import criar_usuario


class CadastroTests(TestCase):
    def _dados(self, **extra):
        return {
            "nome": "Ana Tricolor", "email": "Ana@Coral.com", "data_nascimento": "1995-04-10",
            "senha": "Arruda#Coral2026", "confirmacao": "Arruda#Coral2026", **extra,
        }

    def test_login_tem_link_para_cadastro(self):
        self.assertContains(self.client.get(reverse("web:login")), reverse("web:cadastro"))

    def test_cria_torcedor_e_ja_entra_logado(self):
        resposta = self.client.post(reverse("web:cadastro"), self._dados())
        self.assertRedirects(resposta, reverse("web:consulados"))
        usuario = Usuario.objects.get(email="ana@coral.com")
        self.assertEqual(usuario.tipo_usuario, TipoUsuario.TORCEDOR)
        self.assertEqual(str(usuario.data_nascimento), "1995-04-10")
        self.assertEqual(int(self.client.session["_auth_user_id"]), usuario.pk)

    def test_email_repetido_e_recusado(self):
        criar_usuario(email="ana@coral.com")
        resposta = self.client.post(reverse("web:cadastro"), self._dados())
        self.assertContains(resposta, "Já existe uma conta com este e-mail.")

    def test_senhas_diferentes_e_senha_fraca(self):
        self.assertContains(self.client.post(reverse("web:cadastro"), self._dados(confirmacao="Outra#Senha99")),
                            "As senhas não conferem.")
        self.client.post(reverse("web:cadastro"), self._dados(senha="12345678", confirmacao="12345678"))
        self.assertFalse(Usuario.objects.exists())

    def test_data_de_nascimento_no_futuro_e_recusada(self):
        resposta = self.client.post(reverse("web:cadastro"), self._dados(data_nascimento="2999-01-01"))
        self.assertContains(resposta, "A data de nascimento precisa estar no passado.")
        self.assertFalse(Usuario.objects.exists())
