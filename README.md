# Conexao Coral

Aplicação web do Conexao Coral, com mapa interativo para localizar consulados cadastrados e área de cadastro de novos membros.

## Objetivo

A aplicação tem como foco:
- apresentar a rede Conexao Coral;
- localizar consulados no mapa do Brasil;
- divulgar próximos encontros;
- captar novos membros por meio de um formulário simples;
- manter a identidade visual do clube e da torcida.

## Stack utilizada

- Python 3.12+
- Streamlit
- Pandas

## Estrutura do projeto

- `app.py` — código principal da interface e da lógica da página;
- `assets/logocj2.png` — banner utilizado na página inicial;
- `assets/logocj.png` — imagem utilizada nos pins do mapa;
- `requirements.txt` — dependências para instalação e deploy;
- `main.py/` — pasta com uma versão alternativa do protótipo em NiceGUI, mantida como referência para comparação e evolução.

## Como instalar

1. Abra o terminal na pasta do projeto.
2. Verifique se o Python está disponível.
3. Instale as dependências:

```bash
python -m pip install -r requirements.txt
```

## Como executar

No diretório do projeto, rode:

```bash
python -m streamlit run app.py
```

Ou, em Windows PowerShell:

```powershell
python -m streamlit run app.py
```

Para executar a API compartilhada com Flutter:

```powershell
$env:DATABASE_URL = "postgresql://postgres:SENHA@localhost:5432/conexao_coral"
python -m uvicorn backend.main:app --reload --port 8000
```

Documentação da API: http://localhost:8000/docs

O Streamlit consulta a API em `http://localhost:8000` por padrão. Para usar uma API publicada, defina `CONEXAO_CORAL_API_URL`.

## Mapa de consulados

O mapa consulta a API FastAPI. Se a API estiver indisponível, o app usa temporariamente o registro local de fallback definido em `CONSULADOS`.

Cada registro possui:

- nome do consulado;
- cidade e UF;
- latitude e longitude.

O primeiro registro é o Consulado CoralJampa, em João Pessoa - PB.

## Integração futura com Flutter

O Flutter deve consumir uma API de consulados com operações para:

- listar consulados próximos da localização do usuário;
- cadastrar e atualizar consulados;
- consultar detalhes e contatos;
- sincronizar a mesma base usada pelo mapa web.

O backend FastAPI já está disponível em `backend/main.py`, com PostgreSQL como persistência compartilhada.

## Como a aplicação foi organizada

O arquivo principal foi dividido em funções com responsabilidades bem definidas:

- `configure_page()` — configura a página e o título do navegador;
- `apply_custom_css()` — aplica o visual customizado;
- `render_header()` — monta o cabeçalho principal da Conexao Coral;
- `render_consulate_map()` — exibe busca, mapa e tabela de consulados;
- `render_about_and_events()` — exibe a descrição e os próximos encontros;
- `render_registration_form()` — mostra o formulário de cadastro com validação;
- `render_footer()` — apresenta o rodapé;
- `main()` — centraliza a execução do app.

Essa separação facilita testes, manutenção e futuras alterações sem quebrar a interface inteira.

## Preparar para o GitHub

O repositório não deve conter `.venv`, caches Python, bancos locais ou senhas. Esses itens já estão protegidos pelo `.gitignore`.

Antes do primeiro commit, revise os arquivos staged:

```bash
git status
git diff --cached --stat
```

Configure sua identidade Git, se necessário, e crie o commit:

```bash
git config user.name "Seu Nome"
git config user.email "seu-email@example.com"
git commit -m "Preparar Conexao Coral para web e Flutter"
```

Depois, crie um repositório vazio no GitHub e conecte-o:

```bash
git remote add origin https://github.com/SEU_USUARIO/conexao-coral.git
git push -u origin main
```

## Validação e manutenção

- A execução foi validada com sucesso usando o comando do Streamlit.
- Caso a aplicação não inicie, verifique se a dependência `streamlit` está instalada e se o ambiente Python correto está sendo usado.
- Se for necessário evoluir a página, basta adaptar as funções de renderização sem alterar a estrutura principal do app.

## Observação importante

O projeto inicialmente apresentava duas versões diferentes do mesmo app:
- uma em Streamlit (`app.py`);
- outra em NiceGUI (`main.py/main.py`).

Para manter o projeto consistente e facilitar entendimento, o app principal foi padronizado em Streamlit e documentado com funções e comentários claros.
