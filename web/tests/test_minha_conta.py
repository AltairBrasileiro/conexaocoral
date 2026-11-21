"""Minha conta: dados pessoais, foto do perfil, troca de senha e "esqueci a senha"."""
from __future__ import annotations

import io
import re
import shutil
import tempfile
from datetime import date, timedelta

from django.core import mail
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from PIL import Image
from rest_framework.test import APIClient

from core.models import TokenWhitelist, Usuario
from core.tests.factories import criar_usuario

MEDIA_TESTE = tempfile.mkdtemp(prefix="coral-media-conta-")
SENHA = "SenhaForte#123"  # a senha das contas criadas por ``criar_usuario``
CPF_VALIDO = "529.982.247-25"
OUTRO_CPF_VALIDO = "111.444.777-35"


def tearDownModule():
    shutil.rmtree(MEDIA_TESTE, ignore_errors=True)


def imagem_png(nome: str = "foto.png") -> SimpleUploadedFile:
    buffer = io.BytesIO()
    Image.new("RGB", (40, 40), (227, 6, 19)).save(buffer, format="PNG")
    return SimpleUploadedFile(nome, buffer.getvalue(), content_type="image/png")


class Cenario(TestCase):
    def setUp(self):
        self.usuario = criar_usuario(nome="Joana Tricolor", email="joana@coral.com")
        self.client.force_login(self.usuario)
        self.conta = reverse("web:minha-conta")

    def dados(self, **extra):
        dados = {
            "nome": "Joana Tricolor", "email": "joana@coral.com", "data_nascimento": "1990-05-17",
            "telefone": "(81) 99999-0000", "cpf": CPF_VALIDO, "endereco": "",
        }
        dados.update(extra)
        return dados

    def salvar(self, **extra):
        return self.client.post(reverse("web:atualizar-perfil"), self.dados(**extra))


class DadosPessoaisTests(Cenario):
    def test_pagina_mostra_os_dados_acima_dos_consulados(self):
        pagina = self.client.get(self.conta).content.decode()
        self.assertIn('value="joana@coral.com"', pagina)
        self.assertLess(pagina.index("Meus dados"), pagina.index("Meus consulados"))
        self.assertIn(
            "falta informar o <strong>telefone</strong>, o <strong>CPF</strong> e a <strong>data de nascimento</strong>",
            pagina,
        )

    def test_salva_obrigatorios_e_opcionais(self):
        resposta = self.salvar(
            nome="Joana Coral", email="Joana.Nova@Coral.com", telefone="(81) 99999-0000",
            cpf=CPF_VALIDO, endereco="Rua das Graças, 10 - Recife - PE",
        )
        self.assertRedirects(resposta, self.conta)
        self.usuario.refresh_from_db()
        self.assertEqual(self.usuario.nome, "Joana Coral")
        self.assertEqual(self.usuario.email, "joana.nova@coral.com")
        self.assertEqual(self.usuario.data_nascimento, date(1990, 5, 17))
        self.assertEqual(self.usuario.telefone, "81999990000")
        self.assertEqual(self.usuario.cpf, "52998224725")
        self.assertEqual(self.usuario.endereco, "Rua das Graças, 10 - Recife - PE")
        pagina = self.client.get(self.conta)
        self.assertContains(pagina, 'value="529.982.247-25"')
        self.assertNotContains(pagina, "falta informar")

    def test_endereco_pode_ficar_em_branco(self):
        self.salvar(endereco="Rua A")
        self.assertRedirects(self.salvar(), self.conta)
        self.usuario.refresh_from_db()
        self.assertEqual(self.usuario.endereco, "")

    def test_nome_data_email_telefone_e_cpf_sao_obrigatorios(self):
        for campo, mensagem in (
            ("nome", "Informe o seu nome."),
            ("data_nascimento", "Informe a sua data de nascimento."),
            ("email", "Informe o seu e-mail."),
            ("telefone", "Informe o seu telefone."),
            ("cpf", "Informe o seu CPF."),
        ):
            resposta = self.salvar(**{campo: ""})
            self.assertEqual(resposta.status_code, 200, campo)
            self.assertContains(resposta, mensagem)
        self.usuario.refresh_from_db()
        self.assertIsNone(self.usuario.data_nascimento)

    def test_data_de_nascimento_no_futuro_e_recusada(self):
        amanha = (timezone.localdate() + timedelta(days=1)).isoformat()
        self.assertContains(self.salvar(data_nascimento=amanha), "A data de nascimento precisa estar no passado.")

    def test_cpf_invalido_e_recusado(self):
        for cpf in ("123.456.789-00", "111.111.111-11", "123"):
            self.assertContains(self.salvar(cpf=cpf), "Informe um CPF válido, com 11 dígitos.")
        self.usuario.refresh_from_db()
        self.assertIsNone(self.usuario.cpf)

    def test_cpf_e_email_de_outra_conta_sao_recusados(self):
        criar_usuario(email="outra@coral.com", cpf="52998224725")
        self.assertContains(self.salvar(cpf=CPF_VALIDO), "Este CPF já está cadastrado em outra conta.")
        self.assertContains(self.salvar(email="OUTRA@coral.com"), "Já existe outra conta com este e-mail.")
        self.usuario.refresh_from_db()
        self.assertEqual(self.usuario.email, "joana@coral.com")

    def test_contas_antigas_sem_cpf_continuam_funcionando(self):
        criar_usuario(email="outra@coral.com")
        self.assertRedirects(self.salvar(), self.conta)

    def test_aviso_para_atualizar_o_cadastro_some_depois_de_salvar(self):
        consulados = reverse("web:consulados")
        self.assertContains(self.client.get(consulados), "Atualize o seu cadastro.")
        self.assertNotContains(self.client.get(self.conta), "Atualize o seu cadastro.")  # lá já tem o próprio aviso
        self.assertRedirects(self.salvar(), self.conta)
        self.assertNotContains(self.client.get(consulados), "Atualize o seu cadastro.")
        self.assertNotContains(self.client.get(self.conta), "falta informar")

    def test_exige_login(self):
        self.client.logout()
        for rota in ("web:minha-conta", "web:atualizar-perfil", "web:foto-perfil", "web:trocar-senha"):
            self.assertEqual(self.client.post(reverse(rota)).status_code, 302, rota)


@override_settings(MEDIA_ROOT=MEDIA_TESTE)
class FotoDoPerfilTests(Cenario):
    def enviar(self, arquivo=None):
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.post(reverse("web:foto-perfil"), {"foto": arquivo or imagem_png()})

    def test_envia_troca_e_remove(self):
        self.assertRedirects(self.enviar(), self.conta)
        self.usuario.refresh_from_db()
        primeira = self.usuario.foto.name
        self.assertTrue(primeira.startswith("usuarios/"))
        pagina = self.client.get(self.conta)
        self.assertContains(pagina, self.usuario.foto.url, count=2)  # bolinha do topo e cartão da foto
        self.assertContains(pagina, "Trocar foto")

        self.enviar(imagem_png("outra.png"))
        self.usuario.refresh_from_db()
        self.assertNotEqual(self.usuario.foto.name, primeira)
        self.assertFalse(default_storage.exists(primeira))  # o arquivo antigo não fica sobrando

        segunda = self.usuario.foto.name
        with self.captureOnCommitCallbacks(execute=True):
            self.assertRedirects(self.client.post(reverse("web:remover-foto-perfil")), self.conta)
        self.usuario.refresh_from_db()
        self.assertFalse(self.usuario.foto)
        self.assertFalse(default_storage.exists(segunda))
        self.assertContains(self.client.get(self.conta), "Enviar foto")

    def test_arquivo_que_nao_e_imagem_e_recusado(self):
        resposta = self.enviar(SimpleUploadedFile("nota.txt", b"texto", content_type="text/plain"))
        self.assertEqual(resposta.status_code, 200)
        self.usuario.refresh_from_db()
        self.assertFalse(self.usuario.foto)

    def test_foto_e_opcional(self):
        self.assertRedirects(self.salvar(), self.conta)
        self.assertContains(self.client.get(self.conta), "Enviar foto")


class TrocarSenhaTests(Cenario):
    def trocar(self, **extra):
        dados = {"senha_atual": SENHA, "nova_senha": "OutraSenha#456", "confirmacao": "OutraSenha#456"}
        dados.update(extra)
        return self.client.post(reverse("web:trocar-senha"), dados)

    def test_troca_com_a_senha_atual_e_continua_logado(self):
        self.assertRedirects(self.trocar(), self.conta)
        self.usuario.refresh_from_db()
        self.assertTrue(self.usuario.check_password("OutraSenha#456"))
        self.assertEqual(self.client.get(self.conta).status_code, 200)

    def test_senha_atual_errada_ou_vazia(self):
        self.assertContains(self.trocar(senha_atual="errada"), "A senha atual não confere.")
        self.assertContains(self.trocar(senha_atual=""), "Informe a sua senha atual.")
        self.usuario.refresh_from_db()
        self.assertTrue(self.usuario.check_password(SENHA))

    def test_confirmacao_diferente_senha_fraca_e_senha_repetida(self):
        self.assertContains(self.trocar(confirmacao="Diferente#789"), "As senhas não conferem.")
        self.assertEqual(self.trocar(nova_senha="12345678", confirmacao="12345678").status_code, 200)
        self.assertContains(
            self.trocar(nova_senha=SENHA, confirmacao=SENHA), "A nova senha precisa ser diferente da atual.",
        )
        self.usuario.refresh_from_db()
        self.assertTrue(self.usuario.check_password(SENHA))

    def test_troca_encerra_as_sessoes_do_aplicativo(self):
        api = APIClient()
        login = api.post("/api/v1/auth/login/", {"email": "joana@coral.com", "password": SENHA}, format="json")
        self.assertEqual(login.status_code, 200, login.data)
        self.assertTrue(TokenWhitelist.objects.filter(usuario=self.usuario).exists())
        self.trocar()
        self.assertFalse(TokenWhitelist.objects.filter(usuario=self.usuario).exists())

    def test_pagina_tem_o_botao_esqueci_a_senha(self):
        self.assertContains(self.client.get(self.conta), reverse("web:senha-esqueci"))


class EsqueciASenhaTests(TestCase):
    def setUp(self):
        self.usuario = criar_usuario(nome="Joana Tricolor", email="joana@coral.com")
        self.url = reverse("web:senha-esqueci")

    def link_do_email(self) -> str:
        return re.search(r"https?://[^/]+(/senha/redefinir/\S+)", mail.outbox[0].body).group(1)

    def test_login_tem_o_atalho(self):
        self.assertContains(self.client.get(reverse("web:login")), self.url)

    def test_fluxo_completo_cadastra_nova_senha(self):
        self.assertContains(self.client.get(self.url), "Encontre sua conta")
        resposta = self.client.post(self.url, {"email": "Joana@Coral.com"})
        self.assertRedirects(resposta, reverse("web:senha-enviada"))
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["joana@coral.com"])

        pagina = self.client.get(self.link_do_email(), follow=True)
        self.assertContains(pagina, "Cadastre uma nova senha")
        formulario = pagina.redirect_chain[-1][0]
        resposta = self.client.post(formulario, {"new_password1": "NovaSenha#789", "new_password2": "NovaSenha#789"})
        self.assertRedirects(resposta, reverse("web:senha-redefinida"))
        self.usuario.refresh_from_db()
        self.assertTrue(self.usuario.check_password("NovaSenha#789"))
        # O link só vale uma vez.
        self.assertContains(self.client.get(self.link_do_email(), follow=True), "Link inválido ou expirado")

    def test_email_desconhecido_nao_revela_nada_nem_envia(self):
        resposta = self.client.post(self.url, {"email": "ninguem@coral.com"})
        self.assertRedirects(resposta, reverse("web:senha-enviada"))
        self.assertEqual(len(mail.outbox), 0)

    def test_link_invalido(self):
        pagina = self.client.get(reverse("web:senha-redefinir", args=["MQ", "token-falso"]))
        self.assertContains(pagina, "Link inválido ou expirado")

    def test_logado_ja_vem_com_o_proprio_email(self):
        self.client.force_login(self.usuario)
        self.assertContains(self.client.get(self.url), 'value="joana@coral.com"')


class PerfilPelaApiTests(TestCase):
    def setUp(self):
        self.usuario = criar_usuario(email="joana@coral.com")
        self.api = APIClient()
        self.api.force_authenticate(self.usuario)

    def test_le_e_atualiza_os_novos_campos(self):
        resposta = self.api.patch("/api/v1/usuarios/me/", {
            "data_nascimento": "1990-05-17", "cpf": CPF_VALIDO, "telefone": "81999990000", "endereco": "Rua A, 1",
        }, format="json")
        self.assertEqual(resposta.status_code, 200, resposta.data)
        self.assertEqual(resposta.data["cpf"], "52998224725")
        self.assertEqual(resposta.data["foto"], "")
        self.assertEqual(Usuario.objects.get(pk=self.usuario.pk).data_nascimento, date(1990, 5, 17))

    def test_cpf_invalido_ou_repetido_e_recusado(self):
        criar_usuario(cpf="11144477735")
        for cpf in ("123.456.789-00", OUTRO_CPF_VALIDO):
            resposta = self.api.patch("/api/v1/usuarios/me/", {"cpf": cpf}, format="json")
            self.assertEqual(resposta.status_code, 400, cpf)
        # CPF e telefone são obrigatórios: não podem ser apagados.
        self.assertEqual(self.api.patch("/api/v1/usuarios/me/", {"cpf": ""}, format="json").status_code, 400)
        self.assertEqual(self.api.patch("/api/v1/usuarios/me/", {"telefone": ""}, format="json").status_code, 400)


class MostrarSenhaTests(TestCase):
    """Todo campo de senha tem o botão de olho para o usuário ver ou esconder o que digita."""

    def test_campos_de_senha_tem_o_botao_de_mostrar(self):
        usuario = criar_usuario()
        self.assertContains(self.client.get(reverse("web:login")), "data-mostrar-senha", count=1)
        self.client.force_login(usuario)
        conta = self.client.get(reverse("web:minha-conta"))
        for campo in ("id_senha_atual", "id_nova_senha", "id_confirmacao"):
            self.assertContains(conta, f'data-mostrar-senha="{campo}"')

    def test_nova_senha_pelo_link_tem_o_botao_de_mostrar(self):
        criar_usuario(email="joana@coral.com")
        self.client.post(reverse("web:senha-esqueci"), {"email": "joana@coral.com"})
        link = re.search(r"https?://[^/]+(/senha/redefinir/\S+)", mail.outbox[0].body).group(1)
        pagina = self.client.get(link, follow=True)
        for campo in ("id_new_password1", "id_new_password2"):
            self.assertContains(pagina, f'data-mostrar-senha="{campo}"')
