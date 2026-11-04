# %% [markdown]
# # Modelo CatBoost com previsões conformes
#
# Fit the CatBoost model and write the conformal predictions.

# %%
from argparse import ArgumentParser
from pathlib import Path

import polars as pl
from helpers.paths import repo
from helpers.runtime import notebook_arguments

# %% [markdown]
# ## Argumentos da linha de comando

# %%
parser = ArgumentParser(description="Fit the CatBoost model and write the conformal predictions.")
parser.add_argument("--dataset", type=Path, default=repo() / "files/dataset.parquet", help="Model dataset.")
parser.add_argument(
    "--output", type=Path, default=repo() / "files/predictions.parquet", help="Path of the predictions."
)
args = parser.parse_args(notebook_arguments())

# %% [markdown]
# ## Carregar o conjunto de dados do modelo

# %%
if not args.dataset.exists():
    message = f"missing dataset {args.dataset}"
    raise SystemExit(message)

dataset = pl.read_parquet(args.dataset)
dataset

# %% [markdown]
# ## Ajustar o modelo e exportar as previsões
#
# As variáveis, o alvo e a divisão temporal ainda não estão definidos.
# O CatBoost vai ajustar os regressores de quantil e o MAPIE vai gerar os intervalos conformes.

# %%
message = f"the model is not defined yet ({dataset.height} rows)"
raise NotImplementedError(message)
