# %% [markdown]
# # Períodos de treinamento, validação e teste
#
# Este notebook compara as estatísticas dos períodos de treinamento, validação e teste.
# A análise também compara os períodos anterior e posterior ao lançamento do CS2.
#
# Também apresenta a divisão cronológica prevista para avaliar o modelo.

# %% jupyter={"source_hidden": true}
import polars as pl
from great_tables import GT, md
from great_tables.vals import fmt_integer, fmt_percent
from helpers.evaluation import summarize_evaluation_split
from helpers.export import enable_inline_table_styles, write_outputs
from helpers.formatting import DATE_FORMAT, LOCALE, TABLE_SOURCE, build_metric_table
from helpers.market import get_market_series, summarize_regimes
from helpers.parameters import parameters
from helpers.paths import get_repo_root
from helpers.schemas import read_table

enable_inline_table_styles()

notebook_parameters = parameters().evaluation

paths = parameters().paths

prices_path = get_repo_root() / paths.prices

tables_path = get_repo_root() / paths.tables

tables: dict[str, GT] = {}

PERIOD_LABELS = {"training": "Treinamento", "validation": "Validação", "testing": "Teste"}

REGIME_COLUMNS = [*PERIOD_LABELS, "pre_cs2", "post_cs2"]

REGIME_LABELS = {
    "first_day": "Primeiro dia",
    "last_day": "Último dia",
    "days": "Dias",
    "assets": "Itens",
    "mean_return": "Retorno médio dos itens",
    "geometric_return": "Retorno composto dos itens",
    "std_return": "DP dos retornos dos itens",
    "market_mean_return": "Retorno médio do mercado",
    "market_geometric_return": "Retorno composto do mercado",
    "weighted_mean_return": "Retorno médio do mercado, por preço (2)",
    "market_std_return": "DP do retorno do mercado",
}


prices = read_table("prices", prices_path)

# %% [markdown]
# ## Tamanho da amostra, retornos e volatilidade por período
#
# A tabela apresenta o número de dias e itens, os retornos e a volatilidade de cada período.
# Diferenças entre treinamento, validação e teste descrevem mudanças nas características dos dados.
#
# A análise também compara os períodos anterior e posterior ao lançamento do CS2. O intervalo após o
# lançamento é curto e limita essa comparação.

# %%
market = get_market_series(prices)

regimes = summarize_regimes(prices, market)

regime_values = regimes.with_columns(
    pl.col("first_day", "last_day").dt.strftime(DATE_FORMAT),
    fmt_integer(pl.col("days", "assets"), locale=LOCALE),
    fmt_percent(pl.exclude("regime", "first_day", "last_day", "days", "assets"), decimals=2, locale=LOCALE),
)

regime_summaries = {
    regime: build_metric_table(regime_values.filter(pl.col("regime") == regime), REGIME_LABELS)
    for regime in REGIME_COLUMNS
}

regime_comparison = (
    regime_summaries["training"]
    .rename({"metric_value": "training"})
    .with_columns(**{regime: regime_summaries[regime]["metric_value"] for regime in REGIME_COLUMNS[1:]})
)

tables["regimes"] = (
    GT(regime_comparison, locale=LOCALE)
    .tab_options(table_font_size="7pt")
    .tab_source_note(TABLE_SOURCE)
    .tab_source_note(
        "Retornos diários. O mercado é a média dos retornos dos itens, com ponderação igual ou por preço (2). "
        "DP: desvio padrão."
    )
    .cols_label(
        metric_name=md("**Métrica**"),
        training=md("**Treinamento**"),
        validation=md("**Validação**"),
        testing=md("**Teste**"),
        pre_cs2=md("**Antes do CS2**"),
        post_cs2=md("**Depois do CS2** (1)"),
    )
    .tab_source_note("(1) O lançamento do CS2 ocorreu em 27/09/2023, durante o teste. O intervalo posterior é curto.")
    .tab_source_note("(2) Ponderação pelo preço da observação anterior.")
)

# %% [markdown]
# **Comparação entre períodos — CS:GO**

# %% jupyter={"source_hidden": true}
tables["regimes"]

# %% [markdown]
# ## Divisão cronológica entre treinamento, validação e teste
#
# A limpeza define três períodos consecutivos, sem sorteio de datas ou itens.
# O treinamento define a seleção inicial. A validação escolhe o tamanho da carteira e os parâmetros do modelo.
# O teste avalia as estratégias após essas escolhas. Todos os itens de uma data pertencem ao mesmo período.
#
# Após a validação, o treinamento e a validação formam o histórico disponível para a seleção final.
# Qualquer intervalo adicional entre períodos depende do alvo e do horizonte de previsão do modelo.

# %%
split_summary = summarize_evaluation_split(prices)

evaluation_split = pl.concat(
    [
        split_summary.select(
            pl.lit(label).alias("period"),
            pl.col(f"{period}_start").alias("start"),
            pl.col(f"{period}_end").alias("end"),
            pl.col(f"{period}_days").alias("days"),
            pl.col(f"{period}_records").alias("records"),
        )
        for period, label in PERIOD_LABELS.items()
    ]
).with_columns(pl.col("start", "end").dt.strftime(DATE_FORMAT))

tables["evaluation_split"] = (
    GT(evaluation_split, locale=LOCALE)
    .tab_source_note(TABLE_SOURCE)
    .tab_source_note(
        "A tabela descreve os preços disponíveis. O número de observações utilizáveis depende das variáveis "
        "e do alvo do modelo."
    )
    .fmt_integer(columns=["days", "records"])
    .cols_label(
        period=md("**Período**"),
        start=md("**Início**"),
        end=md("**Fim**"),
        days=md("**Dias** (1)"),
        records=md("**Registros** (2)"),
    )
    .tab_source_note("(1) Contagem de datas distintas com pelo menos um preço observado.")
    .tab_source_note("(2) Cada registro corresponde a um item em uma data, com preço observado.")
)

# %% [markdown]
# **Divisão cronológica entre treinamento, validação e teste — CS:GO**

# %% jupyter={"source_hidden": true}
tables["evaluation_split"]

# %% jupyter={"source_hidden": true, "outputs_hidden": true}
write_outputs(tables, {}, tables_path)
