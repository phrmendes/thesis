# %% [markdown]
# # Sensibilidade dos resultados à limpeza, ao calendário e à carteira
#
# A análise de sensibilidade repete os cálculos com diferentes filtros de limpeza, intervalos entre preços e
# limites de retorno.
#
# Também altera o calendário das promoções e a forma de calcular os preços de entrada e saída. A comparação
# mostra quais resultados permanecem semelhantes nas alternativas avaliadas.
# O tamanho da carteira vem do resumo do buy-and-hold, que deve existir antes desta análise.

# %% jupyter={"source_hidden": true}
import polars as pl
from great_tables import GT, md
from great_tables.vals import fmt_integer
from helpers.export import enable_inline_table_styles, write_outputs
from helpers.formatting import LOCALE, TABLE_SOURCE
from helpers.parameters import parameters
from helpers.paths import get_repo_root
from helpers.schemas import read_table
from helpers.sensitivity import build_sensitivity_row

enable_inline_table_styles()

notebook_parameters = parameters().sensitivity

paths = parameters().paths

tables_path = get_repo_root() / paths.tables

portfolio_path = get_repo_root() / paths.portfolio

sensitivity_path = get_repo_root() / paths.sensitivity

selected_k = int(read_table("portfolio", portfolio_path)["assets"].item())

tables: dict[str, GT] = {}

PRICE_WINDOW_NAME = f"price_window_{notebook_parameters.price_window_days}"

SHIFT_LABELS = {
    shift: pl.select(fmt_integer(pl.lit(shift), force_sign=True, locale=LOCALE)).item()
    for shift in notebook_parameters.sale_shifts
}

VARIANT_LABELS = {
    **{variant.name: variant.label for variant in parameters().sensitivity_variants},
    **{f"sale_shift_{shift}": f"Deslocamento do calendário (dias): {label}" for shift, label in SHIFT_LABELS.items()},
    PRICE_WINDOW_NAME: f"Janela de preços (observações): {notebook_parameters.price_window_days}",
}

variant_prices = {
    variant.name: read_table("prices", sensitivity_path / f"{variant.name}.parquet")
    for variant in parameters().sensitivity_variants
}

baseline = variant_prices["baseline"]

# %% [markdown]
# ## Resultados sob diferentes critérios de limpeza
#
# Cada alternativa usa uma tabela de preços preparada com um critério diferente. A comparação inclui o número
# de itens, o retorno do mercado, os coeficientes das fases e o ROI da carteira.

# %%
cleaning_rows = [build_sensitivity_row(prices, name, selected_k) for name, prices in variant_prices.items()]

# %% [markdown]
# ## Resultados com outras datas de promoção e preços de referência
#
# A fonte não informa o horário exato da coleta diária. A análise desloca o calendário das promoções em um dia
# para cada lado para verificar a sensibilidade a essa definição.
#
# Outra alternativa altera o número de preços observados que compõem a mediana.

# %%
shift_rows = [
    build_sensitivity_row(baseline, f"sale_shift_{shift}", selected_k, shift_days=shift)
    for shift in notebook_parameters.sale_shifts
]

window_rows = [
    build_sensitivity_row(baseline, PRICE_WINDOW_NAME, selected_k, window=notebook_parameters.price_window_days)
]

# %% [markdown]
# ## Resultados de todas as alternativas
#
# A tabela reúne os resultados das alternativas de limpeza, calendário e preços de referência.
#
# O modelo usa $y_t$ para o retorno diário do mercado com ponderação igual na data $t$.
# As variáveis $x_{t1}, \ldots, x_{t5}$ indicam, nessa ordem, a pré-promoção, a primeira metade, a segunda metade,
# a pós-promoção e a virada do ano. Cada variável vale 1 na condição correspondente e 0 nos demais dias.
# A constante é $\beta_0$, os coeficientes das indicadoras são $\beta_1, \ldots, \beta_5$ e $u_t$ representa o erro.
#
# $$
# y_t = \beta_0 + \beta_1 x_{t1} + \cdots + \beta_5 x_{t5} + u_t.
# $$
#
# A análise estima a equação por mínimos quadrados ordinários, com erros-padrão HAC de Newey-West.
# Cada regressão usa a série diária de toda a amostra da alternativa.
# Os coeficientes descrevem associações em relação aos dias fora das fases de promoção, com controle para a
# virada do ano. A tabela apresenta $\beta_2$ e $\beta_4$ com seus p-valores.
#
# O retorno composto do mercado é uma medida descritiva.
# O ROI da carteira vem da simulação buy-and-hold no período de teste, não da regressão.

# %%
summary = pl.concat([*cleaning_rows, *shift_rows, *window_rows]).with_columns(
    pl.col("variant").replace_strict(VARIANT_LABELS, return_dtype=pl.String)
)

tables["sensitivity"] = (
    GT(summary, locale=LOCALE)
    .tab_options(table_font_size="6pt")
    .tab_source_note(TABLE_SOURCE)
    .tab_source_note("Coeficientes do retorno diário do mercado com ponderação igual, como na tabela de fases.")
    .cols_align("left", columns="variant")
    .fmt_integer(columns=["items"])
    .fmt_percent(
        columns=["geometric_return", "fh_coefficient", "post_coefficient", "portfolio_roi"],
        decimals=2,
    )
    .fmt_number(columns=["fh_p_value", "post_p_value"], decimals=3)
    .sub_missing(columns="portfolio_roi", missing_text="Inviável")
    .tab_spanner(label=md("**1ª metade**"), columns=["fh_coefficient", "fh_p_value"])
    .tab_spanner(label=md("**Pós-promoção**"), columns=["post_coefficient", "post_p_value"])
    .cols_label(
        variant=md("**Variante**"),
        items=md("**Itens**"),
        geometric_return=md("**Retorno composto**"),
        fh_coefficient=md("**Coef.**"),
        fh_p_value=md("**p**"),
        post_coefficient=md("**Coef.**"),
        post_p_value=md("**p**"),
        portfolio_roi=md("**ROI da carteira** (3)"),
    )
    .tab_source_note(
        "(1) Cobertura mínima: parcela mínima da mediana diária de preços positivos que o dia precisa atingir."
    )
    .tab_source_note("(2) Mínimo de dias com preço no período de treinamento para o item entrar na amostra.")
    .tab_source_note(
        f"(3) ROI líquido com o tamanho comum de {selected_k} itens, "
        "em ordem decrescente do ROI no histórico de seleção. "
        f"Inviável quando menos de {selected_k} itens atendem aos critérios."
    )
)

# %% [markdown]
# **Sensibilidade dos resultados — CS:GO**

# %% jupyter={"source_hidden": true}
tables["sensitivity"]

# %% [markdown]
# A associação negativa na primeira metade permanece significativa a 5% em todas as alternativas.
# Na pós-promoção, o sinal permanece positivo, mas a significância a 5% depende da alternativa.
# O ROI depende dos filtros e da janela de preços, e a exigência máxima de histórico inviabiliza a carteira
# de tamanho fixo.

# %% jupyter={"source_hidden": true, "outputs_hidden": true}
write_outputs(tables, {}, tables_path)
