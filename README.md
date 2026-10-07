# Dengue e Clima: pipeline de dados e ML para alerta antecipado de surtos

Trabalho final de Engenharia de Dados: pipeline *end-to-end* que integra duas fontes publicas, armazena em PostgreSQL, processa com ETL em Python, cria features e treina um modelo de classificacao.

```
InfoDengue (casos semanais) --\
                               >-> PostgreSQL -> ETL Python -> Features -> ML -> Metricas
Open-Meteo (clima diario) ----/
```

## Problema
Prever se, **daqui a 4 semanas**, um municipio tera **surto de dengue** (incidencia >= 50 casos por 100 mil hab. na semana). Classificacao binaria; metricas: Accuracy, Precision, Recall, F1 e ROC-AUC.

## Fontes de dados
| Fonte | Conteudo | Acesso |
|---|---|---|
| [InfoDengue](https://info.dengue.mat.br) | casos, casos estimados, populacao, incidencia, Rt e nivel de alerta por semana epidemiologica | API `alertcity` |
| [Open-Meteo Archive](https://open-meteo.com) | temperatura, precipitacao e umidade diarias por coordenada | API `archive` |

12 municipios (RJ, SP, BH, Campinas, Goiania, Brasilia, Campo Grande, Salvador, Fortaleza, Recife, Manaus, Curitiba), 2021-2024 (2.496 linhas semanais; 17.532 dias de clima). Os CSVs brutos ja estao em `data/raw/`, entao o projeto roda **sem internet**.

## Estrutura
```
.
|-- data/raw/                  CSVs brutos das duas fontes (versionados)
|-- data/processed/features.csv  base de features (gerada)
|-- sql/01_schema.sql          modelo dimensional PostgreSQL (DDL + views)
|-- src/
|   |-- config.py              parametros, conexao com o banco
|   |-- coleta.py              download das APIs (opcional)
|   |-- etl.py                 extract / transform / validate / load
|   |-- features.py            engenharia de features e alvo
|   |-- modelo.py              treino, comparacao e avaliacao
|   `-- run_pipeline.py        executa tudo
|-- notebooks/
|   |-- 01_analise_exploratoria.ipynb
|   `-- 02_pipeline_final.ipynb   notebook final (ponta a ponta)
|-- models/modelo_surto_dengue.pkl
|-- reports/                   metricas.json, ranking_modelos.csv e graficos
|-- requirements.txt  .env.example
```

## Modelagem no PostgreSQL
Esquema dimensional com chaves e restricoes (ver `sql/01_schema.sql`):
- `dim_municipio` (geocode IBGE, nome, UF, lat/lon)
- `dim_semana` (semana epidemiologica, data inicial, ano, semana)
- `fato_dengue_semana` (PK geocode+se; casos, casos estimados, populacao, incidencia, nivel, Rt)
- `fato_clima_dia` (PK geocode+data; temperaturas, precipitacao, umidade)
- Views: `vw_clima_semana` (clima agregado por semana epidemiologica) e `vw_base_modelo` (juncao dengue + clima)

## ETL (`src/etl.py`)
- **Extract:** le os CSVs de `data/raw`.
- **Transform:** tipagem, remocao de duplicados, preenchimento de nulos (casos, Rt, nivel), interpolacao de lacunas curtas de clima, precipitacao negativa -> 0.
- **Validate:** incidencia >= 0, temperatura e umidade em faixas validas.
- **Load:** recria o schema e carrega (idempotente).

## Features (`src/features.py`)
Todas usam so informacao ate a semana *t* (sem vazamento).
| Grupo | Features |
|---|---|
| Incidencia | atual, lags 1-3, media movel 4s, variacao semanal, tendencia 4s |
| Alerta | nivel de alerta, Rt |
| Clima | temperatura (atual, lag 2, media 4s, minima 4s), chuva (atual, soma 4s e 8s), umidade (atual, media 4s) |
| Sazonalidade/escala | seno/cosseno da semana, log da populacao |

**Alvo:** `surto_futuro` = incidencia em *t+4* >= 50/100 mil.

## Modelagem e avaliacao (`src/modelo.py`)
- Split temporal: treino 2021-2023 (1.788 linhas, 10% surto), teste 2024 (576 linhas, 28,5% surto).
- Modelos: Regressao Logistica, Random Forest, Gradient Boosting (`class_weight=balanced`), mais dois baselines (classe majoritaria e persistencia).
- Selecao por F1 em validacao cruzada temporal (`TimeSeriesSplit`) so no treino.

### Resultados (teste = 2024)
| Modelo | Accuracy | Precision | Recall | F1 | ROC-AUC |
|---|---|---|---|---|---|
| Baseline classe majoritaria | 0,715 | 0,000 | 0,000 | 0,000 | - |
| Baseline persistencia | 0,885 | 0,766 | 0,860 | 0,810 | - |
| **Regressao Logistica (selecionado)** | 0,835 | 0,639 | 0,970 | 0,770 | 0,966 |
| Random Forest | 0,885 | 0,755 | 0,884 | 0,815 | 0,951 |
| Gradient Boosting | 0,892 | 0,783 | 0,860 | 0,820 | 0,957 |

Graficos e metricas completas em `reports/`.

### Interpretacao
- A Regressao Logistica foi selecionada pelo F1 de validacao no treino e tem o maior recall (97%): perde pouquissimos surtos, ao custo de mais falsos alarmes. Em vigilancia epidemiologica isso costuma ser preferivel.
- Os modelos de arvore tem melhor F1 no teste, mas o ganho sobre o baseline de persistencia e pequeno: a incidencia atual ja informa bastante sobre 4 semanas a frente.
- Accuracy isolada engana (a classe majoritaria ja chega a 71%).
- **Limitacoes:** 12 cidades e 4 anos; 2024 foi epidemico (mudanca de distribuicao entre treino e teste); poucos surtos no treino; clima de reanalise, nao de estacoes locais.

## Como executar
Requisitos: Python 3.10+ e PostgreSQL 14+ rodando localmente.

```bash
pip install -r requirements.txt
cp .env.example .env        # (Windows: copy .env.example .env) e ajuste PGPASSWORD
python src/run_pipeline.py  # ETL -> features -> modelo (cria o banco dengue_clima sozinho)
```
Opcoes: `python src/run_pipeline.py --coleta` baixa novamente os dados das APIs. Para o notebook final: `jupyter lab notebooks/02_pipeline_final.ipynb` (executar de dentro de `notebooks/`).

O usuario do PostgreSQL precisa poder criar bancos (ex.: `postgres`).
