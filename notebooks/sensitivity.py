# %% [markdown]
# # Sensibilidade dos resultados às escolhas de limpeza e de carteira
#
# Os limites de limpeza, o tamanho da lacuna aceita entre dois preços, o teto do retorno, a janela dos
# preços de entrada e saída e o calendário das promoções são escolhas do autor. Cada linha abaixo refaz
# o cálculo com uma escolha diferente. Se os resultados mudam pouco, as conclusões não dependem delas.

# %%
from argparse import ArgumentParser
from pathlib import Path

import polars as pl
from great_tables import GT
from helpers.export import inline_table_styles, write_outputs
from helpers.formatting import DEC_MARK, SEP_MARK
from helpers.params import load_params
from helpers.paths import repo
from helpers.runtime import notebook_arguments
from helpers.schemas import read_table
from helpers.sensitivity import sensitivity_row

# %%
# GitHub drops style blocks, so the tables keep their styles inline.
inline_table_styles()

VARIANT_LABELS = {
    "baseline": "Base",
    "day_share_0.3": "Dia aproveitado com 30% da mediana",
    "day_share_0.7": "Dia aproveitado com 70% da mediana",
    "observations_100": "Mínimo de 100 dias de treino (inclui itens mais novos)",
    "observations_200": "Mínimo de 200 dias de treino",
    "observations_500": "Mínimo de 500 dias de treino",
    "gap_3": "Retorno entre preços a até 3 dias",
    "cap_1.0": "Teto do retorno em 100%",
    "cap_2.0": "Teto do retorno em 200%",
    "cap_10.0": "Teto do retorno em 1.000%",
    "sale_shift_-1": "Calendário das promoções um dia antes",
    "sale_shift_1": "Calendário das promoções um dia depois",
    "price_window_1": "Preço de entrada e saída sem suavização",
}

# %% [markdown]
# ## Argumentos da linha de comando

# %%
parser = ArgumentParser(description="Sensibilidade: resume cada variante da limpeza.")
parser.add_argument(
    "--directory",
    type=Path,
    default=repo() / "files/sensitivity",
    help="Pasta com a tabela limpa de cada variante.",
)
parser.add_argument("--k", type=int, default=10, help="Número de itens da carteira.")
parser.add_argument("--tables", type=Path, default=repo() / "output/tables", help="Pasta para os arquivos das tabelas.")
args = parser.parse_args(notebook_arguments())

# %% [markdown]
# ## Refazer os resultados em cada variante da limpeza
#
# Cada variante usa uma tabela limpa com uma escolha diferente. A tabela mostra o número de itens, o
# retorno diário composto do mercado, os coeficientes da primeira metade da promoção e do pós-venda, e o
# ROI da carteira.

# %%
variant_prices = {
    variant["name"]: read_table("prices", args.directory / f"{variant['name']}.parquet")
    for variant in load_params()["sensitivity"]["variants"]
}

cleaning_rows = [sensitivity_row(prices, name, args.k) for name, prices in variant_prices.items()]

# %% [markdown]
# ## Mover o calendário das promoções e a janela de preços
#
# O instante do instantâneo diário não é conhecido. Mover o calendário em um dia para cada lado mostra se
# o resultado das promoções depende desse instante. A janela de preços usa a base, com a mediana trocada
# pelo último preço.

# %%
baseline = variant_prices["baseline"]

shift_rows = [sensitivity_row(baseline, f"sale_shift_{shift}", args.k, shift_days=shift) for shift in (-1, 1)]
window_rows = [sensitivity_row(baseline, "price_window_1", args.k, window=1)]
summary = pl.concat([*cleaning_rows, *shift_rows, *window_rows])

# %% [markdown]
# ## Construir a tabela da tese

# %%
summary_text = summary.with_columns(pl.col("variant").replace_strict(VARIANT_LABELS, return_dtype=pl.String))

summary_gt = (
    GT(summary_text)
    .cols_align("left", columns="variant")
    .tab_header(title="Sensibilidade dos Resultados — CS:GO")
    .fmt_integer(columns=["items"], sep_mark=SEP_MARK)
    .fmt_percent(
        columns=["market_geometric_return", "fh_coefficient", "post_coefficient", "portfolio_roi"],
        decimals=2,
        sep_mark=SEP_MARK,
        dec_mark=DEC_MARK,
    )
    .fmt_number(columns=["fh_p_value", "post_p_value"], decimals=3, sep_mark=SEP_MARK, dec_mark=DEC_MARK)
    .cols_label(
        variant="Variante",
        items="Itens",
        market_geometric_return="Retorno composto do mercado",
        fh_coefficient="1ª metade: coef.",
        fh_p_value="1ª metade: p",
        post_coefficient="Pós-venda: coef.",
        post_p_value="Pós-venda: p",
        portfolio_roi="ROI da carteira",
    )
    .tab_source_note(
        "Coeficientes do retorno diário do mercado com peso igual, como na tabela de fases. "
        f"ROI líquido da carteira com {args.k} itens ordenados pelo ROI de treino."
    )
)
summary_gt

# %% [markdown]
# ## Exportar a tabela LaTeX

# %%
write_outputs({"sensitivity": summary_gt}, {}, args.tables, wide=frozenset({"sensitivity"}))
