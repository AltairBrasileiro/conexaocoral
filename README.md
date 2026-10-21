# Conexão Coral

Projeto 100% Django para consulados de torcedores, partidas, check-ins, eventos e aliados:

* **Interface web** (app `web`): páginas HTML renderizadas pelo Django, com login por sessão.
* **API REST** (app `core`): Django REST Framework, com autenticação JWT (8h) controlada por whitelist.

As duas usam os mesmos services e repositories, então as regras de negócio são idênticas nos dois canais.

## Arquitetura em camadas

```
Requisição → View (HTTP, permissões) → Serializer (validação) → Service (regras) → Repository (ORM) → Model
```

```
conexao_coral/
├── main/                  # Projeto Django: settings.py, urls.py (todas as rotas), wsgi/asgi
└── core/                  # App principal
    ├── models/            # Entidades (um módulo por agregado) + choices + models abstratos
    ├── repositories/      # Acesso a dados; consultas de visibilidade e anotações (evita N+1)
    ├── services/          # Regras de negócio, transações e whitelist de tokens
    ├── serializers/       # Validação de entrada (chama as validações dos services)
    ├── views/             # ViewSets/APIViews, mixins e exception handler
    ├── permissions/       # RBAC: Torcedor, Resp. Consulado, Resp. Aliado, Admin
    ├── authentication/    # WhitelistJWTAuthentication
    ├── filters/           # FilterSets do django-filter
    ├── management/        # Comando limpar_tokens_expirados
    └── tests/             # Testes de integração das regras de negócio
└── web/                   # Interface web (templates Django)
    ├── views.py           # Páginas: mapa, consulado, partidas, aliados, painel (delegam aos services)
    ├── forms.py           # Login por e-mail, dados do consulado, novo evento
    ├── templatetags/      # Formatação em português (datas, plurais, confronto)
    ├── templates/web/     # Templates das páginas
    ├── static/web/        # CSS, JS (mapa com Leaflet + OpenStreetMap) e ícone
    └── tests/             # Testes das páginas
```

## Como rodar

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # por padrão usa SQLite (db.sqlite3)
# Para PostgreSQL: DB_ENGINE=postgres no .env, ajuste as credenciais e rode "createdb conexao_coral"

python manage.py makemigrations core
python manage.py migrate
python manage.py createsuperuser   # vira tipo_usuario=ADMIN
python manage.py popular_demo      # opcional: dados e contas de demo (só com DEBUG=True)
python manage.py runserver
```

Interface web: http://localhost:8000/ (com DEBUG=True, a tela de login mostra as contas de demonstração)

Documentação interativa da API: http://localhost:8000/api/docs/

Testes: `python manage.py test` (API e interface web)

Teste de ponta a ponta dos fluxos do app (banco temporário, sem servidor): `python scripts/testar_api.py`

## JWT com whitelist

| Endpoint | Descrição |
|---|---|
| `POST /api/v1/auth/registro/` | Cadastro público (ADMIN não pode ser escolhido) |
| `POST /api/v1/auth/login/` | Retorna `access` (8h), `refresh` e dados do usuário |
| `POST /api/v1/auth/refresh/` | Rotaciona tokens; refresh antigo sai da whitelist |
| `POST /api/v1/auth/logout/` | Revoga o refresh enviado e o access atual |
| `POST /api/v1/auth/logout-todos/` | Revoga todas as sessões do usuário |

Todo token emitido tem seu `jti` salvo em `TokenWhitelist`. A cada requisição o
token precisa ter assinatura válida **e** estar na whitelist, então o logout tem
efeito imediato. Desativar um usuário ou trocar seu papel também encerra as sessões.
Agende `python manage.py limpar_tokens_expirados` (cron) para manter a tabela enxuta.

## Regras de negócio implementadas

- **Check-in**: 1 check-in ativo por usuário/partida (validação + índice único parcial
  no PostgreSQL contra corrida); o primeiro check-in filia o usuário ao consulado;
  só em consulados aprovados e dentro da janela configurável (`CHECKIN_HORAS_ANTES/DEPOIS`).
- **Presença em evento**: só membros do consulado organizador, em evento aprovado e não encerrado; uma vez por evento.
- **Moderação**: consulados, eventos e aliados nascem `PENDENTE` (exceto se criados por admin).
  Edição relevante do dono em registro aprovado volta para `PENDENTE`.
- **Eventos exclusivos**: só aparecem na listagem para membros do consulado.
- **Selo verificado**: apenas para aliados aprovados (garantido também por `CheckConstraint`).

## Produção (https://conexaocoral.com.br)

O app Android usa `https://conexaocoral.com.br/api/v1`. No servidor (Linux):

```bash
pip install -r requirements.txt
cp .env.production.example .env        # preencha chaves, banco e domínio
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py createsuperuser
gunicorn main.wsgi:application --bind 0.0.0.0:8000 --workers 3
```

- **HTTPS é obrigatório**: o APK só aceita conexões seguras. Coloque um proxy com
  certificado (nginx + Let's Encrypt, ou o TLS da própria hospedagem) na frente do
  gunicorn e repasse o cabeçalho `X-Forwarded-Proto`.
- **DNS**: aponte `conexaocoral.com.br` (e `www`) para o servidor.
- **Estáticos** (admin, Swagger) são servidos pelo WhiteNoise; **imagens** da pasta
  `media/` pelo Django enquanto `SERVIR_MEDIA=True`. Com mais tráfego, sirva `media/` pelo
  nginx/CDN e desligue a opção. A pasta `media/` precisa de armazenamento persistente.
- **Dados de demonstração**: `popular_demo` cria contas com senha pública e por isso
  se recusa a rodar com `DEBUG=False`. Para uma vitrine controlada:
  `python manage.py popular_demo --forcar --url-base https://conexaocoral.com.br`
  (o `--url-base` grava os links das imagens com o domínio público).
- Verificação: `python manage.py check --deploy`.
