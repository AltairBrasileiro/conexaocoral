# Conexão Coral

Projeto 100% Django para consulados de torcedores, partidas, eventos e aliados:

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
    ├── views_aliados.py   # Lojista: "Meus negócios" (cadastrar, editar e excluir o próprio negócio)
    ├── views_admin.py     # Administração: negócios, usuários e partidas (abas do Painel do Administrador)
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

- **Solicitação de consulado**: qualquer torcedor solicita o cadastro (página "Solicitar novo
  consulado", com os requisitos do clube em `CONEXAO_CORAL["REQUISITOS_CONSULADO"]`, foto do local
  opcional e grupo do WhatsApp obrigatório); uma solicitação em análise por vez. O admin aceita ou
  recusa (com motivo) na aba "Solicitações" do painel; ao aceitar, o torcedor vira embaixador.
  Até a aprovação, o consulado só aparece para quem o solicitou (e para o admin), fica fora do mapa
  e não pode ser editado nem receber membros.
- **Entrar e sair de consulados**: o torcedor pede para ser membro e o embaixador aprova ou recusa
  em "Gerenciar membros"; o membro sai quando quiser (o embaixador não sai do próprio consulado).
  Tudo isso também fica em "Minha conta", junto com os eventos com presença confirmada.
- **Grupo do WhatsApp**: o link só é exibido para membros do consulado (e para o embaixador e o
  admin), na página, no mapa e na API.
- **Membros e cargos**: o embaixador cadastra membros (por e-mail; sem conta, cria uma conta de
  torcedor com senha provisória), remove membros e define cargos, exibidos na página pública.
  Membros com cargo acessam o Painel para editar as fotos do consulado, gerenciar os eventos e ver as
  listas de confirmados.
- **Eventos**: o embaixador, os membros com cargo (ou o admin) criam, editam e excluem os eventos do consulado, publicados
  na hora, com até 6 fotos e limite de vagas opcional.
- **Presença em eventos**: eventos livres aceitam qualquer torcedor; os exclusivos só aparecem (e só
  aceitam confirmação) para membros. O torcedor desmarca a presença até o início do evento. O
  embaixador, os membros com cargo e o admin veem a lista de confirmados, retiram pessoas (que não
  conseguem confirmar de novo, até serem readmitidas) e exportam a lista em PDF.
- **Minha conta**: cada usuário atualiza os próprios dados (nome, data de nascimento e e-mail
  obrigatórios; telefone, CPF e endereço opcionais), envia, troca ou remove a foto do perfil e troca a
  senha informando a atual. O CPF e o e-mail não podem repetir os de outra conta. As regras ficam no
  `UsuarioService`.
- **Esqueci a senha**: na tela de login e em "Minha conta". O usuário informa o e-mail e recebe um
  link de uso único, válido por 1 hora, para cadastrar a nova senha. Trocar ou redefinir a senha
  encerra as sessões do aplicativo. O envio usa as variáveis `EMAIL_*` do `.env`; sem `EMAIL_HOST`,
  o e-mail é só impresso no terminal do servidor (desenvolvimento).
- **Carona Coral**: exclusiva dos membros de cada consulado. Qualquer membro oferece carona; só os
  membros daquele consulado veem e reservam vaga. Membros de outros consulados (e quem saiu) não
  oferecem nem veem as caronas dele.
- **Reportes**: qualquer usuário envia problemas ou sugestões ("Reportar problema ou sugestão", no menu
  do perfil); só administradores veem, na aba "Reportes" do painel, e marcam como resolvidos.
- **Apoie o app**: página com Pix (QR Code e copia e cola) configurado em `CONEXAO_CORAL["PIX"]`
  (por enquanto com chave fictícia e aviso de demonstração).
- **Ícone do consulado**: é o pino do consulado no mapa. O embaixador, os membros com cargo e o admin
  enviam, trocam e removem a imagem pelo Painel ("Ícone no mapa"); sem ícone, o mapa usa o pino padrão.
- **Lojista (Vitrine da Torcida)**: qualquer usuário cadastra o próprio negócio em "Meus negócios", com
  Instagram, WhatsApp e foto opcionais; o dono edita e exclui o que cadastrou (até 5 por conta). Ao
  aprovar o negócio de um torcedor, ele vira Responsável por Aliado (lojista).
- **Moderação de aliados**: nascem `PENDENTE` (exceto se criados por admin) e só aparecem na vitrine
  depois de aprovados; edição do dono em aliado já avaliado volta para `PENDENTE`. A recusa pode levar
  um motivo, que o dono vê.
- **Administração sem Django Admin**: o Painel do Administrador tem as abas Consulados, Solicitações
  (novos consulados), Negócios (aprovar, recusar, selo, tirar da vitrine), Usuários (busca, troca de
  papel, bloquear/liberar acesso), Partidas (cadastrar, editar, excluir) e Reportes. O Django Admin
  continua em `/admin/`, só para superusuários.
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
