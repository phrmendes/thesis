# %% [markdown]
# # Desenho da avaliação dos resultados
#
# Este caderno define como o modelo e a carteira serão julgados. Primeiro compara os regimes do mercado: o
# treino contra o teste, e os dias antes contra os dias depois do lançamento do CS2. Depois mostra os folds
# da avaliação com janela crescente.

# %%
from argparse import ArgumentParser
from pathlib import Path

import polars as pl
from great_tables import GT
from helpers.evaluation import walk_forward_splits
from helpers.export import inline_table_styles, write_outputs
from helpers.formatting import SEP_MARK, metric_text_table
from helpers.market import market_series, regime_summary
from helpers.params import load_params
from helpers.paths import repo
from helpers.runtime import notebook_arguments
from helpers.schemas import read_table

# %%
# GitHub drops style blocks, so the tables keep their styles inline.
inline_table_styles()

REGIME_COLUMNS = ["training", "testing", "pre_cs2", "post_cs2"]

REGIME_LABELS = {
    "first_day": "Primeiro dia",
    "last_day": "Último dia",
    "days": "Dias",
    "assets": "Itens",
    "mean_return": "Retorno diário médio dos itens",
    "geometric_return": "Retorno diário composto dos itens",
    "std_return": "Desvio padrão dos retornos dos itens",
    "market_mean_return": "Retorno diário médio do mercado (peso igual)",
    "market_geometric_return": "Retorno diário composto do mercado (peso igual)",
    "weighted_mean_return": "Retorno diário médio do mercado (peso por preço)",
    "market_std_return": "Desvio padrão do retorno do mercado (peso igual)",
    "market_lag_1": "Autocorrelação do mercado (defasagem 1)",
    "adf_return_p_value": "Teste ADF do retorno do mercado (p-valor)",
}

REGIME_FORMATS = {
    "first_day": "%d/%m/%Y",
    "last_day": "%d/%m/%Y",
    "days": "d",
    "assets": "d",
    "mean_return": ".2%",
    "geometric_return": ".2%",
    "std_return": ".2%",
    "market_mean_return": ".2%",
    "market_geometric_return": ".2%",
    "weighted_mean_return": ".2%",
    "market_std_return": ".2%",
    "market_lag_1": ".4f",
    "adf_return_p_value": ".3f",
}

# %% [markdown]
# ## Argumentos da linha de comando

# %%
parser = ArgumentParser(description="Avaliação: regimes do mercado e folds com janela crescente.")
parser.add_argument("--prices", type=Path, default=repo() / "files/prices.parquet", help="Preços diários limpos.")
parser.add_argument("--tables", type=Path, default=repo() / "output/tables", help="Pasta para os arquivos das tabelas.")
args = parser.parse_args(notebook_arguments())

# %%
prices = read_table("prices", args.prices)
market = market_series(prices)

# %% [markdown]
# ## Comparar os regimes do mercado
#
# O período de teste contém a transição para o CS2. Comparar treino e teste, e os dias antes e depois do
# lançamento do CS2, mostra se retorno, volatilidade e persistência mudam de regime. Uma mudança enfraquece
# qualquer avaliação fora da amostra, da carteira ao modelo. O período depois do lançamento é curto.

# %%
regimes = regime_summary(prices, market)
regime_texts = {
    regime: metric_text_table(regimes.filter(pl.col("regime") == regime), REGIME_LABELS, REGIME_FORMATS)
    for regime in REGIME_COLUMNS
}

regimes_text = (
    regime_texts["training"]
    .rename({"metric_value": "training"})
    .with_columns(**{regime: regime_texts[regime]["metric_value"] for regime in REGIME_COLUMNS[1:]})
)

regimes_gt = (
    GT(regimes_text)
    .tab_header(title="Comparação entre Regimes — CS:GO")
    .cols_label(
        metric_name="Métrica", training="Treino", testing="Teste", pre_cs2="Antes do CS2", post_cs2="Depois do CS2"
    )
    .tab_source_note(
        "O mercado é a média dos retornos diários dos itens, com peso igual ou com o preço do dia anterior com preço. "
        "O CS2 foi lançado em 27/09/2023, dentro do teste. O período depois do lançamento é curto."
    )
)
regimes_gt

# %% [markdown]
# ## Definir os folds da avaliação
#
# O modelo será avaliado com janelas de treino crescentes e um dia de embargo entre treino e teste. Vários
# folds mostram se o desempenho muda com o regime, o que uma única divisão 70/30 não mostra.

# %%
eval_params = load_params()["eval"]

folds = walk_forward_splits(
    prices["date"].unique().to_list(),
    eval_params["initial_days"],
    eval_params["step_days"],
    eval_params["horizon_days"],
)

folds_text = folds.with_columns(
    pl.col("train_end").dt.strftime("%d/%m/%Y"),
    pl.col("test_start").dt.strftime("%d/%m/%Y"),
    pl.col("test_end").dt.strftime("%d/%m/%Y"),
)

folds_gt = (
    GT(folds_text.select("fold", "train_days", "train_end", "test_start", "test_end", "test_days"))
    .tab_header(title="Folds da Avaliação com Janela Crescente — CS:GO")
    .fmt_integer(columns=["fold", "train_days", "test_days"], sep_mark=SEP_MARK)
    .cols_label(
        fold="Fold",
        train_days="Dias de treino",
        train_end="Fim do treino",
        test_start="Início do teste",
        test_end="Fim do teste",
        test_days="Dias de teste",
    )
    .tab_source_note(
        "O treino começa no primeiro dia e cresce a cada fold. Um dia de embargo separa treino e teste. "
        "Os dias contam só dias com preço."
    )
)
folds_gt

# %% [markdown]
# ## Exportar tabelas LaTeX

# %%
write_outputs({"regimes": regimes_gt, "walk_forward": folds_gt}, {}, args.tables)
