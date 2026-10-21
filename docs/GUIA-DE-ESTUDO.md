# Guia de estudo

Conceitos usados neste projeto, na ordem sugerida de estudo. Para cada um: o que é, onde aparece no código, um exercício
e onde aprender mais. Depois de cada exercício, rode `pytest`.

## Parte 1: Coleta de dados

### 1. Consumir uma API pública

A API do SGS responde com JSON a uma URL do tipo
`https://api.bcb.gov.br/dados/serie/bcdata.sgs.433/dados?formato=json&dataInicial=01/01/2026&dataFinal=31/10/2026`.
Os parâmetros vão na **query string**. Datas vêm como `dd/MM/aaaa` e valores como texto, então precisam de conversão.

- **No código:** `BCBClient._fetch_window` em [`bcb.py`](../src/indicadores/bcb.py).
- **Exercício:** abra a URL acima no navegador e compare com o que `indicadores resumo` mostra.
- **Leia:** [Portal de dados abertos do BCB](https://dadosabertos.bcb.gov.br/) e
  [httpx: Quickstart](https://www.python-httpx.org/quickstart/).

### 2. Paginação por janelas de tempo

Para séries diárias, a API recusa consultas de mais de 10 anos. A solução é quebrar o período em janelas de 5 anos e
juntar os resultados. É o mesmo raciocínio da paginação de qualquer API.

- **No código:** `_windows` e `_add_years` em `bcb.py`.
- **Para pensar:** por que `_add_years` precisa tratar o 29 de fevereiro?

### 3. Resiliência: retries e backoff exponencial

Redes e servidores falham de vez em quando (a primeira execução deste projeto pegou um `502`). Erros **temporários**
(`429`, `5xx`, queda de conexão) valem nova tentativa, com espera crescente (1s, 2s, 4s) para não sobrecarregar o
servidor. Erros do **cliente** (`400`) não melhoram tentando de novo, então falham na hora.

- **No código:** `BCBClient._get_json` e `RETRYABLE_STATUS`.
- **Exercício:** adicione *jitter* (um pequeno tempo aleatório) ao backoff. Pesquise por que isso ajuda.
- **Leia:** [AWS: Exponential backoff and jitter](https://aws.amazon.com/blogs/architecture/exponential-backoff-and-jitter/).

## Parte 2: Engenharia de dados

### 4. ETL e carga incremental

**ETL** = *Extract, Transform, Load*: extrair da fonte, transformar no formato desejado e carregar no destino. Baixar
tudo de novo a cada dia seria desperdício, então a **carga incremental** busca só a partir da última data salva, com 45
dias de sobreposição para pegar dados revisados ou publicados com atraso.

- **No código:** [`pipeline.py`](../src/indicadores/pipeline.py).
- **Exercício:** rode `indicadores atualizar` duas vezes seguidas e veja que a segunda traz "0 novas".

### 5. Idempotência e upsert

Uma operação **idempotente** pode rodar várias vezes com o mesmo resultado. O **upsert** (*update + insert*) junta os
dados novos aos antigos, mantém um valor por data e deixa a versão mais recente vencer. Por isso a sobreposição do item
anterior não duplica nada.

- **No código:** `CsvStore.upsert` em [`storage.py`](../src/indicadores/storage.py).
- **Para pensar:** por que CSV e não SQLite aqui? (Dica: como fica o `git diff` de cada um depois de uma atualização?)

### 6. pandas e séries temporais

Um `DataFrame` é uma tabela; uma `Series` é uma coluna com índice. Com um índice de datas, `resample("MS")` agrupa por
mês, `rolling(12)` cria janelas móveis e `pct_change` calcula variações.

- **No código:** [`analysis.py`](../src/indicadores/analysis.py).
- **Exercício:** crie `accumulated_year_to_date`, a inflação acumulada no ano, e um teste para ela.
- **Leia:** [pandas: 10 minutes to pandas](https://pandas.pydata.org/docs/user_guide/10min.html) e
  [Time series](https://pandas.pydata.org/docs/user_guide/timeseries.html).

### 7. A matemática dos indicadores

- **Acumulado em 12 meses:** inflação compõe, não soma. Doze meses de 1% dão 12,68%, não 12%:
  `(1,01 × 1,01 × ... × 1,01) − 1`.
- **Juro real (equação de Fisher):** `(1 + Selic) / (1 + inflação) − 1`. Com Selic de 13,75% e IPCA de 4,58%, o juro
  real é ~8,8%, e não 9,17% como a subtração simples daria.
- **Ex-post vs. ex-ante:** aqui se usa a inflação *passada*; o mercado costuma usar a inflação *esperada* (Focus).

- **No código:** `accumulated` e `real_interest`; os testes em [`test_pipeline.py`](../tests/test_pipeline.py)
  conferem essas contas.

## Parte 3: Visualização

### 8. Streamlit

Streamlit transforma um script Python em app web: cada interação reexecuta o script de cima a baixo. Por isso existe o
`@st.cache_data`, que evita reler os CSVs a cada clique. Componentes como `st.metric`, `st.tabs` e `st.slider` montam a
interface.

- **No código:** [`app.py`](../app.py).
- **Exercício:** adicione um `st.multiselect` para escolher quais séries aparecem no gráfico de juros.
- **Leia:** [Streamlit: Get started](https://docs.streamlit.io/get-started).

### 9. Gráficos com Plotly

Plotly Express gera gráficos interativos (zoom, tooltip) a partir de um DataFrame. Ele espera dados no formato
**longo** (uma linha por data e série), por isso o código usa `melt` para converter do formato **largo** (uma coluna
por série).

- **No código:** `line_chart` em `app.py`.
- **Exercício:** imprima o DataFrame antes e depois do `melt` e compare.
- **Leia:** [Plotly Express](https://plotly.com/python/plotly-express/).

## Parte 4: Automação e qualidade

### 10. GitHub Actions agendado (cron)

`schedule` roda um workflow num horário definido pela sintaxe **cron** (`17 22 * * 1-5` = 22:17 UTC, de segunda a
sexta). O workflow coleta, faz commit só se algo mudou e escreve um resumo na página da execução. `workflow_dispatch`
permite rodar manualmente pela aba Actions. `concurrency` impede duas coletas ao mesmo tempo.

- **No código:** [`.github/workflows/update-data.yml`](../.github/workflows/update-data.yml).
- **Exercício:** vá em Actions → Atualizar dados → Run workflow e acompanhe a execução.
- **Atenção:** o GitHub desativa workflows agendados de repositórios sem atividade por 60 dias.
- **Leia:** [Eventos que disparam workflows: schedule](https://docs.github.com/en/actions/writing-workflows/choosing-when-your-workflow-runs/events-that-trigger-workflows#schedule)
  e [crontab.guru](https://crontab.guru/).

### 11. Testes com transporte simulado

Testes que dependem da internet são lentos e instáveis. `httpx.MockTransport` intercepta as requisições e devolve
respostas montadas no teste: dá para simular `502`, `404` e datas futuras sem acessar a API. O pipeline também é testado
com um cliente falso.

- **No código:** [`tests/test_bcb.py`](../tests/test_bcb.py).
- **Exercício:** escreva um teste para uma resposta com `valor` vazio (`""`). O que o código faz hoje? E o que deveria
  fazer?

### 12. Empacotamento e CLI

O `pyproject.toml` define dependências principais e **extras** opcionais (`[dashboard]`, `[dev]`), para que o workflow
de coleta não instale Streamlit à toa. `argparse` com **subcomandos** cria `indicadores atualizar` e `indicadores resumo`.

- **No código:** [`pyproject.toml`](../pyproject.toml) e [`cli.py`](../src/indicadores/cli.py).

## Próximos passos

- **Expectativas do mercado:** puxar o Boletim Focus (API Olinda do BCB) e calcular o juro real ex-ante.
- **Banco analítico:** trocar os CSVs por DuckDB ou Parquet e comparar o desempenho.
- **Alertas:** mandar um e-mail ou mensagem no Telegram quando a Selic mudar.
- **Orquestração:** reescrever o pipeline com Prefect ou Airflow.
