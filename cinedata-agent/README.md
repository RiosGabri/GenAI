# CineData Analytics — Text-to-SQL Agent

Agente em Python para consultar o catálogo Gold da CineData Analytics em linguagem natural.

## 1. Pré-requisitos

- Python 3.10+
- `cinerocket.db`
- uma chave da OpenRouter

O banco deve ficar na raiz do projeto:

```text
cinedata-agent/
├── cinerocket.db
├── main.py
└── app/
```

## 2. Instalação

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 3. Configuração

Copie:

```bash
cp .env.example .env
```

Edite `.env` e coloque sua chave:

```text
OPENROUTER_API_KEY=sua_chave
OPENROUTER_MODEL=openrouter/free
CINEDATA_DB_PATH=cinerocket.db
```

Antes de executar, carregue as variáveis do `.env` na sessão ou use uma ferramenta
como `python-dotenv` no entrypoint. Para uso simples no terminal:

```bash
export $(grep -v '^#' .env | xargs)
```

## 4. Executar

```bash
python3 main.py
```

Exemplos:

```text
Quais são os 10 filmes com maior receita em R$?

Qual é o lucro médio por gênero considerando apenas filmes com receita informada?

Quais são os 5 filmes mais populares?

Quais filmes têm maior divergência entre a nota TMDB e a nota IMDb?
```

## 5. Testes

```bash
pytest -q
```

Os testes atuais verificam principalmente o guardrail que impede SQL de escrita
ou múltiplas instruções.

## 6. Arquitetura

```text
Pergunta
   |
   v
LLM via OpenRouter
   |
   v
SQL SELECT/WITH
   |
   v
SQL Guard
   |
   v
SQLite cinerocket.db
   |
   v
Resultado
```

## 7. Segurança

O agente não aceita:

- INSERT
- UPDATE
- DELETE
- DROP
- ALTER
- CREATE
- ATTACH
- DETACH
- PRAGMA
- transações
- múltiplas instruções

A aplicação abre o SQLite e executa somente a consulta gerada depois da validação.

## 8. Próximas extensões

A estrutura foi preparada para receber:

- conjunto de avaliação com perguntas esperadas;
- geração de resposta natural separada da geração de SQL;
- observabilidade de SQL e erros;
- retry quando o SQL for inválido;
- fallback entre modelos;
- cache;
- API FastAPI;
- interface web;
- gráficos;
- guardrails adicionais.
