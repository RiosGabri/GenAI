# CineData Analytics — Agente Text-to-SQL (GenAI)

Agente em Python que recebe perguntas em português, gera **uma consulta SQL somente de leitura** com um LLM (via OpenRouter), executa no `cinerocket.db` (camada Gold da CineData) e devolve a tabela de resultado com uma explicação curta.

> O agente não "sabe" as respostas: todo número vem do banco. O LLM só traduz a pergunta em SQL e, opcionalmente, narra o resultado.

---

## 1. Pré-requisitos

- Python 3.10+
- `cinerocket.db` (SQLite com as tabelas Gold) na raiz do projeto
- Chave de API do OpenRouter (`sk-or-v1-...`), gratuita, em <https://openrouter.ai/keys>

## 2. Instalação

```bash
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## 3. Configuração

Crie um arquivo `.env` na raiz do projeto. O `python-dotenv` o carrega automaticamente (não é preciso exportar nada no terminal):

```text
OPENROUTER_API_KEY=sk-or-v1-sua_chave
OPENROUTER_MODEL=openrouter/free
OPENROUTER_FALLBACK_MODELS=google/gemma-4-26b-a4b-it:free,z-ai/glm-5.2:free
CINEDATA_DB_PATH=cinerocket.db
```

> Nunca versione o `.env`. Confirme que ele está no `.gitignore`.

### Variáveis disponíveis

| Variável | Padrão | Função |
|---|---|---|
| `OPENROUTER_API_KEY` | — (obrigatória) | Chave do OpenRouter |
| `OPENROUTER_MODEL` | `openrouter/free` | Modelo principal |
| `OPENROUTER_FALLBACK_MODELS` | vazio | Modelos extras, separados por vírgula, tentados em ordem se o principal falhar (429, 5xx, modelo inexistente) |
| `CINEDATA_DB_PATH` | `cinerocket.db` | Caminho do banco |
| `MAX_ROWS` | `100` | Máximo de linhas devolvidas |
| `MAX_SQL_LENGTH` | `8000` | Tamanho máximo do SQL gerado |
| `MAX_SQL_ATTEMPTS` | `2` | Tentativas de gerar SQL válido por pergunta |
| `QUERY_TIMEOUT_SECONDS` | `5` | Tempo máximo de execução de cada consulta |
| `REQUEST_TIMEOUT_SECONDS` | `60` | Timeout de cada chamada ao LLM |
| `NARRATE_ANSWER` | `true` | Faz uma 2ª chamada ao LLM para explicar o resultado em português |
| `SHOW_SQL` | `false` | Mostra o SQL executado e as tentativas descartadas |
| `OPENROUTER_SITE_URL` / `OPENROUTER_SITE_NAME` | vazio / `CineData Analytics Agent` | Cabeçalhos opcionais de identificação |

## 4. Executar

```bash
python3 main.py
```

Digite a pergunta no prompt (`sair` encerra). Exemplos:

```text
Quais são os 10 filmes com maior receita em R$?
Qual é o lucro médio por gênero considerando apenas filmes com receita informada?
Quais são os 5 filmes mais populares?
Quais filmes têm maior divergência entre a nota TMDB e a nota IMDb?
Qual dupla ator-diretor mais trabalhou junta?
Diretores com maior nota média (mínimo de 5 filmes)
```

Para ver o SQL gerado, use `SHOW_SQL=true` no `.env`.

## 5. Como funciona

```text
Pergunta
   │
   ▼
Prompt = regras + schema lido do banco + valores distintos + referência temporal
   │
   ▼
LLM (OpenRouter) ── falhou? ──► próximo modelo da lista de fallback
   │
   ▼
Resposta é "ESCLARECIMENTO: ..."?  ── sim ──► devolve a dúvida ao usuário (nada é executado)
   │ não
   ▼
SQL Guard (valida o texto)
   │
   ▼
SQLite somente leitura + timeout + limite de linhas
   │         └─ erro de SQL/validação? devolve o erro ao LLM e tenta de novo
   ▼
Tabela formatada (R$, US$, números em pt-BR) + explicação em português
```

Pontos de projeto:

- **Schema dinâmico.** `database.py` lê tabelas, colunas, PK/FK direto do banco, não de um texto fixo. Também injeta no prompt os valores distintos de `tipo_pessoa`, `nome_genero` e `status_filme` (o modelo erra `Ator` vs `ator` se não os vê) e a **referência temporal** para "últimos N anos" (maior `ano_lancamento` entre filmes com status `Lançado`; filmes planejados têm anos futuros e não contam).
- **Regras de negócio no prompt** (`prompts.py`): valores em R$ por padrão (`*_brl`); "informado" = não nulo e > 0; margem só com receita e orçamento > 0; "nota" sem qualificação = `nota_imdb`; mínimos em `HAVING COUNT(DISTINCT ...)`; cuidado com tabelas bridge, que multiplicam linhas; sem N explícito, `LIMIT 10`.
- **Esclarecimento em vez de chute.** Se a pergunta for ambígua de forma que muda o resultado, o modelo responde com `ESCLARECIMENTO:` e o agente não executa nada.
- **Retry com feedback.** Se o SQL for inválido ou falhar no SQLite, a mensagem de erro volta ao LLM para correção, até `MAX_SQL_ATTEMPTS`.
- **Fallback de modelos.** Modelos `:free` ficam lotados com frequência (erro 429). Um modelo que retorna 404 é descartado pelo resto da sessão para não gastar cota.
- **Resiliência da narração.** Se a explicação falhar, o resultado do banco é entregue mesmo assim.

## 6. Segurança (defesa em camadas)

| Camada | Onde | O que faz |
|---|---|---|
| 1. Conexão somente leitura | `database.py` | Abre o SQLite com `mode=ro` e `PRAGMA query_only = ON`. Mesmo que um `DELETE` passasse, o banco o rejeita |
| 2. SQL Guard | `sql_guard.py` | Remove cercas markdown; exige que a resposta seja só `SELECT`/`WITH`; bloqueia `INSERT/UPDATE/DELETE/DROP/ALTER/CREATE/ATTACH/DETACH/VACUUM/REINDEX/PRAGMA`; proíbe múltiplas instruções |
| 3. Leitura "cega" a literais | `sql_guard.py` | Remove strings, identificadores entre aspas e comentários antes da varredura, então títulos como `Drop Dead Fred` ou `A View to a Kill` não são bloqueados por engano |
| 4. Timeout | `database.py` | Consultas que passam de `QUERY_TIMEOUT_SECONDS` são interrompidas (`QueryTimeoutError`) |
| 5. Limite de linhas | `database.py` | Devolve no máximo `MAX_ROWS` e avisa quando o resultado foi truncado |

A chave da API nunca é impressa e vem apenas do ambiente.

## 7. Cota do OpenRouter (importante)

Sem créditos comprados, o plano gratuito permite **50 requisições por dia** (20/min), com reset à meia-noite UTC (**21h em Brasília**). Requisições que falham **também contam**.

Por isso o agente:

- usa `max_retries=0` no SDK (o SDK repetiria 429/5xx sozinho e queimaria cota);
- limita as tentativas de SQL (`MAX_SQL_ATTEMPTS`);
- informa, ao fim de cada resposta, quantas chamadas ao modelo a pergunta consumiu e qual modelo respondeu.

Uma pergunta custa de 1 a 3 chamadas no caso normal (SQL + eventual retry + narração), mais as chamadas gastas em modelos que falharam. Para economizar, use `NARRATE_ANSWER=false`.

Erros comuns:

| Sintoma | Causa provável | O que fazer |
|---|---|---|
| `Chave do OpenRouter inválida` (401) | Chave ausente ou errada | Confira `OPENROUTER_API_KEY` |
| `Nenhum modelo respondeu` | Pool do modelo lotado (429 do provider) ou cota diária esgotada | Configure `OPENROUTER_FALLBACK_MODELS` ou aguarde o reset |
| `Banco não encontrado` | `cinerocket.db` fora do lugar | Coloque na raiz ou ajuste `CINEDATA_DB_PATH` |
| `não consegui gerar um SQL válido` | O modelo errou em todas as tentativas | Reformule a pergunta; use `SHOW_SQL=true` para ver as tentativas |

## 8. Testes

```bash
pytest -q
```

Os testes **não gastam cota**: o cliente do LLM é substituído por um `FakeClient`.

| Arquivo | Cobre |
|---|---|
| `test_sql_guard.py` | Aceita `SELECT`/`WITH`; remove `;` final e cercas markdown; aceita palavras proibidas dentro de literais; rejeita escrita, `PRAGMA`, múltiplas instruções, texto fora do SQL |
| `test_database.py` | Leitura, conexão somente leitura, truncamento, timeout de consulta recursiva, schema lido do banco, banco inexistente, caminho com acento/espaço |
| `test_formatting.py` | Formatação pt-BR de R$/US$, casas decimais, valores nulos, truncamento de textos longos |
| `test_agent.py` | Fluxo completo com cliente falso: sucesso em 1 chamada, retry com erro devolvido ao modelo, desistência sem tocar no banco, esclarecimento, fallback em 429, descarte de modelo 404, narração opcional |

## 9. Estrutura

```text
cinedata-agent/
├── cinerocket.db            # não versionado (ver seção 1)
├── main.py                  # CLI interativa
├── requirements.txt
├── .env                     # não versionado
├── app/
│   ├── agent.py             # orquestra: LLM → guard → SQLite → narração
│   ├── config.py            # variáveis de ambiente
│   ├── database.py          # conexão read-only, schema dinâmico, timeout
│   ├── formatting.py        # tabela e números em pt-BR
│   ├── prompts.py           # prompts de SQL, narração e retry
│   └── sql_guard.py         # validação do SQL
└── tests/
    ├── conftest.py
    ├── test_agent.py
    ├── test_database.py
    ├── test_formatting.py
    └── test_sql_guard.py
```

## 10. Limitações conhecidas

- **Correção semântica não é verificada.** O guard garante que o SQL é seguro, não que responde à pergunta. Modelos gratuitos podem escolher a coluna errada ou esquecer um filtro; a mitigação é o prompt com regras e exemplos, e `SHOW_SQL=true` para auditar.
- **Sem memória de conversa.** Cada pergunta é independente; não há "e se for só 2020?" referindo-se à anterior.
- **O guard é por regex.** É uma segunda camada; a proteção real contra escrita é a conexão somente leitura.
- **Dependência de modelos gratuitos.** Disponibilidade e qualidade variam ao longo do dia.
- **Prompt acoplado ao domínio.** Regras como "nota = IMDb" e os exemplos são específicos da CineData.

## 11. Próximos passos possíveis

- Conjunto de avaliação com perguntas e respostas esperadas (execução automática do SQL de referência)
- Memória curta de conversa
- API FastAPI e interface web com gráficos
- Cache de perguntas repetidas
