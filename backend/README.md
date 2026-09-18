# API da Conexao Coral

## PostgreSQL

Defina a URL de conexão antes de iniciar a API:

```powershell
$env:DATABASE_URL = "postgresql://postgres:SENHA@localhost:5432/conexao_coral"
```

Para subir um PostgreSQL local com Docker:

```powershell
docker compose up -d postgres
$env:DATABASE_URL = "postgresql://postgres:postgres@localhost:5432/conexao_coral"
```

Em produção, configure `DATABASE_URL` no serviço de hospedagem. Não coloque a senha diretamente no código ou no repositório.

Crie previamente o banco `conexao_coral` no PostgreSQL. As tabelas e o registro inicial do Consulado CoralJampa são criados automaticamente na primeira inicialização da API.

## Executar localmente

Na raiz do projeto:

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --reload --port 8000
```

Documentacao interativa: http://localhost:8000/docs

## Endpoints

- `GET /health`
- `GET /consulados?busca=PB`
- `GET /consulados?latitude=-7.12&longitude=-34.85&raio_km=50`
- `POST /consulados`
- `PUT /consulados/{id}`
- `DELETE /consulados/{id}`

A persistência usa PostgreSQL por meio de `DATABASE_URL`. O Streamlit consulta `http://localhost:8000` por padrão; para apontar para uma API publicada, defina `CONEXAO_CORAL_API_URL`.
