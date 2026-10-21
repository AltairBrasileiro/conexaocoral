"""
Teste de ponta a ponta (smoke test) da API Conexão Coral.

Percorre, via HTTP, os fluxos usados pelas telas do app: cadastro/login,
mapa de consulados, calendário de partidas, check-in, eventos, aliados e
painel do responsável. Roda em um banco temporário criado só para o teste
(o ``db.sqlite3`` não é tocado) e não precisa do servidor no ar.

Uso:
    .venv\\Scripts\\python.exe scripts\\testar_api.py
"""
from __future__ import annotations

import logging
import os
import sys
from datetime import timedelta
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "main.settings")

import django  # noqa: E402

django.setup()

from django.core.cache import cache  # noqa: E402
from django.db import connection  # noqa: E402
from django.test.utils import setup_test_environment, teardown_test_environment  # noqa: E402
from django.utils import timezone  # noqa: E402
from rest_framework.test import APIClient  # noqa: E402

from core.models import TipoUsuario, Usuario  # noqa: E402

SENHA = "SenhaForte#123"
API = "/api/v1"

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Respostas 4xx são esperadas em vários passos; os logs só poluiriam o relatório.
for nome_logger in ("django.request", "core"):
    logging.getLogger(nome_logger).setLevel(logging.CRITICAL)


class Roteiro:
    """Executa as verificações, imprime o resultado de cada uma e acumula falhas."""

    def __init__(self) -> None:
        self.total = 0
        self.falhas: list[str] = []

    def secao(self, titulo: str) -> None:
        print(f"\n== {titulo} ==")

    def verificar(self, descricao: str, condicao: bool, detalhe: object = "") -> bool:
        self.total += 1
        if condicao:
            print(f"  [OK]    {descricao}")
        else:
            print(f"  [FALHA] {descricao}")
            if detalhe:
                print(f"          -> {detalhe}")
            self.falhas.append(descricao)
        return condicao

    def status(self, descricao: str, resposta, esperado: int) -> bool:
        detalhe = f"HTTP {resposta.status_code}: {getattr(resposta, 'data', '')}"
        return self.verificar(f"{descricao} (HTTP {esperado})", resposta.status_code == esperado, detalhe)


def cliente() -> APIClient:
    return APIClient()


def registrar(r: Roteiro, nome: str, email: str, tipo: str) -> None:
    cache.clear()  # evita o throttle de 10 req/min do escopo "auth"
    resposta = cliente().post(f"{API}/auth/registro/", {
        "nome": nome, "email": email, "tipo_usuario": tipo,
        "password": SENHA, "password_confirmacao": SENHA,
    })
    r.status(f"Registro de {nome} ({tipo})", resposta, 201)


def logar(r: Roteiro, email: str) -> tuple[APIClient, dict]:
    cache.clear()
    c = cliente()
    resposta = c.post(f"{API}/auth/login/", {"email": email, "password": SENHA})
    r.status(f"Login de {email}", resposta, 200)
    c.credentials(HTTP_AUTHORIZATION=f"Bearer {resposta.data.get('access', '')}")
    return c, resposta.data


def resultados(resposta) -> list[dict]:
    """Aceita respostas paginadas ({results: [...]}) ou listas simples."""
    dados = resposta.data
    return dados.get("results", []) if isinstance(dados, dict) else list(dados)


def executar(r: Roteiro) -> None:
    # ------------------------------------------------------------------ Auth
    r.secao("Cadastro e login")
    registrar(r, "Torcedor Coral", "torcedor@coral.com", TipoUsuario.TORCEDOR)
    registrar(r, "Embaixador Coral", "embaixador@coral.com", TipoUsuario.RESPONSAVEL_CONSULADO)
    registrar(r, "Lojista Coral", "lojista@coral.com", TipoUsuario.RESPONSAVEL_ALIADO)

    cache.clear()
    resposta = cliente().post(f"{API}/auth/registro/", {
        "nome": "Intruso", "email": "intruso@coral.com", "tipo_usuario": TipoUsuario.ADMIN,
        "password": SENHA, "password_confirmacao": SENHA,
    })
    r.status("Registro público não permite papel ADMIN", resposta, 400)

    # O admin não pode se cadastrar pela API; é criado direto no banco.
    Usuario.objects.create_superuser(email="admin@coral.com", password=SENHA, nome="Admin Coral")

    torcedor, _ = logar(r, "torcedor@coral.com")
    embaixador, _ = logar(r, "embaixador@coral.com")
    lojista, _ = logar(r, "lojista@coral.com")
    admin, _ = logar(r, "admin@coral.com")

    resposta = torcedor.get(f"{API}/usuarios/me/")
    r.status("Perfil do usuário logado", resposta, 200)
    r.verificar("Perfil retorna o papel TORCEDOR", resposta.data.get("tipo_usuario") == TipoUsuario.TORCEDOR)
    r.status("Acesso sem token é negado", cliente().get(f"{API}/consulados/"), 401)

    # --------------------------------------------------- Consulados (mapa)
    r.secao("Mapa e consulados")
    r.status("Torcedor não cria consulado", torcedor.post(f"{API}/consulados/", {
        "nome": "Pirata", "endereco": "Rua X", "latitude": "-8.05", "longitude": "-34.9",
    }), 403)

    resposta = embaixador.post(f"{API}/consulados/", {
        "nome": "Consulado Coral Tambaú",
        "descricao": "Bar oficial da torcida em João Pessoa",
        "endereco": "Av. Tamandaré, 100 - Tambaú, João Pessoa/PB",
        "latitude": "-7.115000",
        "longitude": "-34.823000",
        "link_whatsapp": "https://chat.whatsapp.com/ConviteCoral",
    })
    r.status("Responsável cria consulado", resposta, 201)
    consulado_id = resposta.data.get("id")
    r.verificar("Consulado nasce PENDENTE", resposta.data.get("status_aprovacao") == "PENDENTE")

    visiveis = [c["id"] for c in resultados(torcedor.get(f"{API}/consulados/"))]
    r.verificar("Consulado pendente não aparece para o torcedor", consulado_id not in visiveis)

    r.status("Responsável não aprova o próprio consulado",
             embaixador.post(f"{API}/consulados/{consulado_id}/aprovar/"), 403)
    resposta = admin.post(f"{API}/consulados/{consulado_id}/aprovar/")
    r.status("Admin aprova consulado", resposta, 200)

    resposta = torcedor.get(f"{API}/consulados/", {"search": "Tambaú"})
    r.status("Busca de consulados por localidade", resposta, 200)
    achados = resultados(resposta)
    r.verificar("Busca encontra o consulado aprovado", any(c["id"] == consulado_id for c in achados), achados)
    if achados:
        c = achados[0]
        r.verificar("Consulado traz coordenadas e link do WhatsApp",
                    bool(c.get("latitude") and c.get("longitude") and c.get("link_whatsapp")), c)

    # --------------------------------------------------------- Partidas
    r.secao("Calendário de partidas")
    dados_partida = {
        "adversario": "Sport",
        "mando_campo": "CASA",
        "campeonato": "Campeonato Pernambucano",
        "data_hora": (timezone.now() + timedelta(hours=1)).isoformat(),  # dentro da janela de check-in
        "canal_transmissao": "TV Coral",
    }
    r.status("Torcedor não cria partida", torcedor.post(f"{API}/partidas/", dados_partida), 403)
    resposta = admin.post(f"{API}/partidas/", dados_partida)
    r.status("Admin cria partida", resposta, 201)
    partida_id = resposta.data.get("id")

    resposta = torcedor.get(f"{API}/partidas/proximas/")
    r.status("Lista das próximas partidas", resposta, 200)
    proxima = next((p for p in resposta.data if p["id"] == partida_id), {})
    r.verificar("Partida traz adversário, mando, campeonato e transmissão",
                all(proxima.get(k) for k in ("adversario", "mando_campo", "campeonato", "canal_transmissao")),
                proxima)

    # --------------------------------------------------------- Check-in
    r.secao("Check-in")
    resposta = torcedor.get(f"{API}/consulados/{consulado_id}/")
    r.verificar("Torcedor ainda não é membro antes do check-in", resposta.data.get("eh_membro") is False)

    resposta = torcedor.post(f"{API}/checkins/", {"partida": partida_id, "consulado": consulado_id})
    r.status("Torcedor faz check-in", resposta, 201)
    checkin_id = resposta.data.get("id")

    resposta = torcedor.get(f"{API}/consulados/{consulado_id}/")
    r.verificar("Primeiro check-in torna o torcedor membro", resposta.data.get("eh_membro") is True)
    # O responsável já é membro desde a criação; o torcedor é o segundo.
    r.verificar("Consulado passa a ter 2 membros (responsável + torcedor)",
                resposta.data.get("total_membros") == 2, resposta.data)

    r.status("Segundo check-in na mesma partida é recusado",
             torcedor.post(f"{API}/checkins/", {"partida": partida_id, "consulado": consulado_id}), 400)

    resposta = torcedor.get(f"{API}/partidas/{partida_id}/ranking-consulados/")
    r.status("Ranking de check-ins da partida", resposta, 200)
    ranking = {item["id"]: item["total_checkins"] for item in resposta.data}
    r.verificar("Contador de check-ins do consulado = 1", ranking.get(consulado_id) == 1, resposta.data)

    r.status("Torcedor cancela o check-in", torcedor.post(f"{API}/checkins/{checkin_id}/cancelar/"), 200)
    r.status("Após cancelar, novo check-in é aceito",
             torcedor.post(f"{API}/checkins/", {"partida": partida_id, "consulado": consulado_id}), 201)

    # ---------------------------------------------------------- Eventos
    r.secao("Eventos do consulado")
    inicio = timezone.now() + timedelta(days=2)
    dados_evento = {
        "consulado": consulado_id,
        "titulo": "Resenha pós-jogo",
        "descricao": "Encontro da torcida no bar",
        "data_hora_inicio": inicio.isoformat(),
        "data_hora_fim": (inicio + timedelta(hours=3)).isoformat(),
    }
    r.status("Torcedor não cria evento", torcedor.post(f"{API}/eventos/", dados_evento), 403)
    resposta = embaixador.post(f"{API}/eventos/", dados_evento)
    r.status("Responsável cria evento", resposta, 201)
    evento_id = resposta.data.get("id")
    r.verificar("Evento nasce PENDENTE", resposta.data.get("status_aprovacao") == "PENDENTE")
    r.status("Admin aprova evento", admin.post(f"{API}/eventos/{evento_id}/aprovar/"), 200)

    resposta = torcedor.get(f"{API}/eventos/", {"consulado": consulado_id})
    r.status("Torcedor lista os eventos do consulado", resposta, 200)
    r.verificar("Lista contém o evento aprovado", any(e["id"] == evento_id for e in resultados(resposta)))

    resposta = torcedor.post(f"{API}/presencas-evento/", {"evento": evento_id})
    r.status("Membro confirma presença", resposta, 201)
    r.status("Presença duplicada é recusada",
             torcedor.post(f"{API}/presencas-evento/", {"evento": evento_id}), 400)

    registrar(r, "Visitante", "visitante@coral.com", TipoUsuario.TORCEDOR)
    visitante, _ = logar(r, "visitante@coral.com")
    r.status("Não membro não confirma presença",
             visitante.post(f"{API}/presencas-evento/", {"evento": evento_id}), 400)

    # ------------------------------------------------ Painel do responsável
    r.secao("Painel do responsável")
    resposta = embaixador.get(f"{API}/consulados/", {"sou_responsavel": "true"})
    r.status("Responsável lista os consulados que administra", resposta, 200)
    r.verificar("Lista contém o consulado dele", any(c["id"] == consulado_id for c in resultados(resposta)))

    resposta = embaixador.get(f"{API}/checkins/", {"partida": partida_id, "consulado": consulado_id, "ativo": "true"})
    r.status("Responsável consulta check-ins do consulado", resposta, 200)

    resposta = embaixador.get(f"{API}/eventos/{evento_id}/presencas/")
    r.status("Responsável vê presenças confirmadas no evento", resposta, 200)
    r.verificar("Evento tem 1 presença confirmada", len(resultados(resposta)) == 1, resposta.data)

    r.status("Torcedor não vê a lista de presenças",
             torcedor.get(f"{API}/eventos/{evento_id}/presencas/"), 403)
    r.status("Torcedor não vê os membros do consulado",
             torcedor.get(f"{API}/consulados/{consulado_id}/membros/"), 403)

    resposta = embaixador.patch(f"{API}/consulados/{consulado_id}/", {"descricao": "Aberto a partir das 16h"})
    r.status("Responsável atualiza dados do consulado", resposta, 200)

    # ---------------------------------------------------------- Aliados
    r.secao("Aliados")
    dados_aliado = {
        "nome_negocio": "Camisas do Coral",
        "categoria": "LOJA",
        "descricao": "Vestuário da torcida",
        "link_instagram": "https://instagram.com/camisasdocoral",
        "link_whatsapp": "https://wa.me/5583999999999",
    }
    r.status("Torcedor não cadastra aliado", torcedor.post(f"{API}/aliados/", dados_aliado), 403)
    r.status("Link de Instagram inválido é recusado",
             lojista.post(f"{API}/aliados/", {**dados_aliado, "link_instagram": "https://exemplo.com/x"}), 400)
    resposta = lojista.post(f"{API}/aliados/", dados_aliado)
    r.status("Responsável por aliado cadastra negócio", resposta, 201)
    aliado_id = resposta.data.get("id")

    r.status("Admin aprova aliado", admin.post(f"{API}/aliados/{aliado_id}/aprovar/"), 200)
    resposta = admin.post(f"{API}/aliados/{aliado_id}/conceder-selo/")
    r.status("Admin concede selo de verificação", resposta, 200)
    r.verificar("Aliado fica com selo verificado", resposta.data.get("selo_verificado") is True)

    resposta = torcedor.get(f"{API}/aliados/", {"categoria": "LOJA"})
    r.status("Torcedor filtra aliados por categoria", resposta, 200)
    r.verificar("Filtro retorna o aliado verificado",
                any(a["id"] == aliado_id and a["selo_verificado"] for a in resultados(resposta)))

    # ----------------------------------------------------------- Logout
    r.secao("Logout")
    cache.clear()
    _, tokens = logar(r, "torcedor@coral.com")
    sessao = cliente()
    sessao.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
    r.status("Logout revoga a sessão", sessao.post(f"{API}/auth/logout/", {"refresh": tokens["refresh"]}), 204)
    r.status("Token revogado deixa de funcionar", sessao.get(f"{API}/usuarios/me/"), 401)


def main() -> int:
    setup_test_environment()
    nome_original = connection.settings_dict["NAME"]
    connection.creation.create_test_db(verbosity=0, autoclobber=True)
    roteiro = Roteiro()
    try:
        executar(roteiro)
    except Exception as exc:  # erro inesperado também conta como falha
        roteiro.verificar("Execução sem erros inesperados", False, repr(exc))
        raise
    finally:
        connection.creation.destroy_test_db(nome_original, verbosity=0)
        teardown_test_environment()

        aprovados = roteiro.total - len(roteiro.falhas)
        print(f"\nResultado: {aprovados}/{roteiro.total} verificações OK")
        if roteiro.falhas:
            print("Falhas:")
            for falha in roteiro.falhas:
                print(f"  - {falha}")
    return 1 if roteiro.falhas else 0


if __name__ == "__main__":
    sys.exit(main())
