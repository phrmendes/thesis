# %% [markdown]
# # Modelo CatBoost com previsões conformes
#
# O modelo estima quantis de retorno com intervalos conformes, para dar às previsões uma incerteza
# calibrada. Este caderno é só o esqueleto. Ainda faltam definir as variáveis, o alvo e a divisão
# temporal.

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
#
# O conjunto de dados do modelo depende de uma etapa de preparação que ainda não existe. Falhar cedo,
# com uma mensagem clara, evita um erro difícil de entender mais adiante.

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
#
# O ajuste fica adiado até a definição das variáveis, do alvo e da divisão temporal. Este bloco lança
# um erro de propósito, para que ninguém confunda o esqueleto com um modelo pronto.

# %%
message = f"the model is not defined yet ({dataset.height} rows)"
raise NotImplementedError(message)
