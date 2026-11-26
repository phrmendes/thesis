# %% [markdown]
# # Retornos diários e risco dos itens de CS:GO
#
# Este notebook descreve os retornos diários dos itens, sua distribuição e as diferenças por raridade e faixa
# de preço.
#
# Cada retorno exige preços observados em dois dias consecutivos. A análise não preenche preços ausentes, pois
# isso criaria retornos iguais a zero e saltos artificiais.

# %% jupyter={"source_hidden": true}
import altair as alt
import polars as pl
from great_tables import GT, md
from great_tables.vals import fmt_percent
from helpers.export import enable_inline_table_styles, write_outputs
from helpers.formatting import FONT_FAMILY, HELPER_PARAMETERS, LOCALE, TABLE_SOURCE, build_cap_text, wrap_chart_note
from helpers.parameters import parameters
from helpers.paths import get_repo_root
from helpers.returns import (
    calculate_item_measures,
    calculate_return_statistics,
    estimate_measure_densities,
    summarize_return_distribution,
)
from helpers.schemas import read_table
from helpers.segments import build_price_segment, build_rarity_segment, summarize_segments

alt.renderers.enable("png", embed_options={"formatLocale": LOCALE, "timeFormatLocale": LOCALE})

CHART_CONFIG = alt.Config(
    font=FONT_FAMILY,
    title=alt.TitleConfig(anchor=HELPER_PARAMETERS.title_anchor, align=HELPER_PARAMETERS.title_align),
    legend=alt.LegendConfig(orient=HELPER_PARAMETERS.legend_orient),
)

enable_inline_table_styles()

notebook_parameters = parameters().returns

paths = parameters().paths

prices_path = get_repo_root() / paths.prices

tables_path = get_repo_root() / paths.tables

images_path = get_repo_root() / paths.images

tables: dict[str, GT] = {}

charts: dict[str, alt.TopLevelMixin] = {}

CAP_TEXT = build_cap_text()

LABEL_MAP = {"rest": "Restante (1)", "overall": "Geral (1)"}

DISTRIBUTION_LABELS = {"capped": f"Limitado ({CAP_TEXT})", "raw": "Bruto"}

CENTRAL_COLUMNS = ["mean_return", "median_return", "geometric_return", "min_return", "max_return"]

prices = read_table("prices", prices_path)

bin_width = notebook_parameters.bin_width


def build_segment_table(frame: pl.DataFrame, label: str, note: str) -> GT:
    """Build the table of one segment summary.

    Returns:
        The formatted table.

    """
    return (
        GT(frame.with_columns(pl.col("segment").cast(pl.String)), locale=LOCALE)
        .tab_source_note(TABLE_SOURCE)
        .tab_source_note(
            f"{note} "
            "N. de observações: cada registro corresponde a um item em uma data. "
            "O mesmo item pode aparecer em várias datas."
        )
        .tab_options(table_font_size="8pt")
        .cols_align("left", columns="segment")
        .fmt_integer(columns=["items", "item_days"])
        .fmt_number(columns=["median_price"], decimals=2)
        .fmt_percent(columns=["mean_return", "std_return"], decimals=2)
        .fmt_percent(columns=["zero_share"], decimals=1)
        .cols_label(
            segment=md(f"**{label}**"),
            items=md("**Itens**"),
            item_days=md("**N. de observações**"),
            median_price=md("**Preço mediano (US$)**"),
            mean_return=md("**Média**"),
            std_return=md("**DP**"),
            zero_share=md("**Retorno zero**"),
        )
    )


# %% [markdown]
# ## Retorno e risco por item
#
# A tabela apresenta medidas diárias de retorno e risco. A classificação inclui apenas itens com observações
# suficientes para reduzir a influência de históricos curtos.
#
# As linhas Restante e Geral resumem os retornos dos demais itens e do conjunto completo, respectivamente.
#
# Os índices de Sharpe e Sortino permanecem na frequência diária. A análise não os anualiza, pois a
# autocorrelação dos retornos impede o uso direto da regra da raiz quadrada.

# %%
returns = calculate_return_statistics(prices).with_columns(pl.col("name").replace(LABEL_MAP))

asset_rows = list(range(returns.height - 2))

pooled_rows = [returns.height - 2, returns.height - 1]

tables["returns"] = (
    GT(returns.select("name", *CENTRAL_COLUMNS, "n_days"), locale=LOCALE)
    .tab_options(table_font_size="8pt")
    .tab_source_note(TABLE_SOURCE)
    .tab_source_note(
        f"Retornos diários limitados em {CAP_TEXT}. Ranking pelo retorno composto entre itens com "
        f"{HELPER_PARAMETERS.item_min_days} dias ou mais de retorno."
    )
    .fmt_percent(columns=CENTRAL_COLUMNS, decimals=2)
    .fmt_number(columns=["n_days"], rows=asset_rows, decimals=0)
    .fmt_number(columns=["n_days"], rows=pooled_rows, decimals=1)
    .tab_spanner(label=md("**Retornos**"), columns=CENTRAL_COLUMNS)
    .cols_label(
        name=md("**Item**"),
        mean_return=md("**Média**"),
        median_return=md("**Mediana**"),
        geometric_return=md("**Composto**"),
        min_return=md("**Mínimo**"),
        max_return=md("**Máximo**"),
        n_days=md("**Dias**"),
    )
    .tab_source_note(
        "(1) Restante reúne os retornos diários dos itens fora do ranking. Geral reúne os retornos de todos os itens."
    )
)

# %% [markdown]
# **Retornos diários por item — CS:GO**

# %% jupyter={"source_hidden": true}
tables["returns"]

# %% [markdown]
# A tabela seguinte apresenta o risco dos mesmos itens, na mesma ordem.

# %%
tables["returns_risk"] = (
    GT(returns.select("name", "std_return", "negative_returns_std", "sharpe", "sortino"), locale=LOCALE)
    .tab_options(table_font_size="10pt")
    .tab_source_note(TABLE_SOURCE)
    .tab_source_note(
        "DP: desvio padrão. DP neg.: desvio padrão dos retornos negativos. Razões diárias com taxa livre de risco zero."
    )
    .fmt_percent(columns=["std_return", "negative_returns_std"], decimals=2)
    .fmt_number(columns=["sharpe", "sortino"], decimals=2)
    .cols_label(
        name=md("**Item**"),
        std_return=md("**DP**"),
        negative_returns_std=md("**DP neg.**"),
        sharpe=md("**Sharpe**"),
        sortino=md("**Sortino** (2)"),
    )
    .tab_source_note(
        "(1) Restante reúne os retornos diários dos itens fora do ranking. Geral reúne os retornos de todos os itens."
    )
    .tab_source_note(
        "(2) O Sortino divide a média dos retornos diários pelo desvio-padrão amostral dos retornos negativos."
    )
)

# %% [markdown]
# **Risco dos retornos diários por item — CS:GO**

# %% jupyter={"source_hidden": true}
tables["returns_risk"]

# %% [markdown]
# ## Distribuição dos retornos
#
# A comparação entre retornos brutos e limitados mostra como o limite altera a média, o desvio padrão e as
# caudas da distribuição.
#
# Na análise anterior, um teto de 100% reduziu em mais de 90% a soma dos retornos logarítmicos de um item.
# Movimentos que dobram o preço podem representar mudanças permanentes, não apenas ruído.
#
# A análise de sensibilidade compara outros tetos.

# %%
distribution = summarize_return_distribution(prices).with_columns(
    pl.col("label").replace_strict(DISTRIBUTION_LABELS, return_dtype=pl.String)
)

large_return_label = pl.select(fmt_percent(pl.lit(notebook_parameters.large_return), decimals=0, locale=LOCALE)).item()

tables["distribution"] = (
    GT(distribution.select("label", "n", "mean", "geometric_mean", "std", "skewness", "excess_kurtosis"), locale=LOCALE)
    .tab_options(table_font_size="9.5pt")
    .tab_source_note(TABLE_SOURCE)
    .tab_source_note(
        "DP: desvio padrão. Retornos de todos os itens reunidos. O retorno bruto não tem limite. "
        f"O limite de {CAP_TEXT} reduz a média e o desvio padrão. Com ruído de preço, a média aritmética supera "
        "a mediana e o retorno composto."
    )
    .fmt_percent(columns=["mean", "geometric_mean", "std"], decimals=2)
    .fmt_number(columns=["skewness", "excess_kurtosis"], decimals=2)
    .fmt_integer(columns=["n"])
    .cols_label(
        label=md("**Retorno**"),
        n=md("**Observações**"),
        mean=md("**Média**"),
        geometric_mean=md("**Composto**"),
        std=md("**DP**"),
        skewness=md("**Assimetria**"),
        excess_kurtosis=md("**Curtose em excesso**"),
    )
)

# %% [markdown]
# **Momentos dos retornos diários — CS:GO**

# %% jupyter={"source_hidden": true}
tables["distribution"]

# %% [markdown]
# A tabela seguinte mostra os percentis das mesmas distribuições.

# %%
tables["distribution_quantiles"] = (
    GT(distribution.select("label", "p01", "p05", "p50", "p95", "p99", "share_above_half"), locale=LOCALE)
    .tab_source_note(TABLE_SOURCE)
    .tab_source_note(
        "P: percentil. A última coluna mostra a parcela das observações com retorno absoluto acima do limite."
    )
    .fmt_percent(columns=["p01", "p05", "p50", "p95", "p99", "share_above_half"], decimals=2)
    .cols_label(
        label=md("**Retorno**"),
        p01=md("**P1**"),
        p05=md("**P5**"),
        p50=md("**P50**"),
        p95=md("**P95**"),
        p99=md("**P99**"),
        share_above_half=md(f"**|r| > {large_return_label}**"),
    )
)

# %% [markdown]
# **Percentis dos retornos diários — CS:GO**

# %% jupyter={"source_hidden": true}
tables["distribution_quantiles"]

# %% [markdown]
# Os painéis separam os retornos brutos e limitados, com as mesmas escalas para permitir a comparação.
# A escala logarítmica do eixo vertical mantém visíveis as caudas raras.
# O limite do eixo horizontal altera apenas a exibição. Valores acima dele não entram na última faixa visível.

# %%
is_visible_return = pl.col("retorno") <= notebook_parameters.raw_ceiling

return_series = {"Limitado": prices["return"], "Bruto": prices["raw_return"]}

return_bins = pl.concat(
    [
        pl.DataFrame({"retorno": series, "serie": label})
        .drop_nulls("retorno")
        .filter(is_visible_return)
        .with_columns(((pl.col("retorno") / bin_width).floor() * bin_width).alias("faixa"))
        .group_by("serie", "faixa")
        .agg(pl.len().alias("itens_dia"))
        for label, series in return_series.items()
    ]
).sort("serie", "faixa")

charts["returns_histogram"] = (
    alt.Chart(return_bins)
    .mark_line(color="black", interpolate="step-after")
    .encode(
        x=alt.X(
            "faixa:Q",
            title="Retorno diário",
            axis=alt.Axis(format=".0%"),
            scale=alt.Scale(domainMax=notebook_parameters.raw_ceiling),
        ),
        y=alt.Y("itens_dia:Q", title="N. de observações", scale=alt.Scale(type="log")),
    )
    .properties(width=HELPER_PARAMETERS.chart_width // 2, height=HELPER_PARAMETERS.chart_height)
    .facet(column=alt.Column("serie:N", title=None, sort=["Bruto", "Limitado"]))
    .resolve_scale(x="shared", y="shared")
    .properties(
        title=alt.Title(
            wrap_chart_note(
                "N. de observações: retornos válidos de itens em cada faixa.",
                "O mesmo item pode contribuir em várias datas.",
            ),
            anchor="start",
            orient="bottom",
            fontSize=10,
            fontWeight="normal",
        ),
        config=CHART_CONFIG,
    )
)

# %% [markdown]
# **Distribuição dos retornos diários**

# %% jupyter={"source_hidden": true}
charts["returns_histogram"]

# %% [markdown]
# ## Distribuição das medidas de retorno e risco entre os itens
#
# A figura reúne as distribuições da média aritmética, da mediana, do desvio-padrão e da média geométrica dos
# retornos diários por item.
#
# Cada item conta uma vez, desde que tenha observações suficientes.
# O intervalo dos gráficos usa os percentis e a margem definidos nos parâmetros.
# A média geométrica considera a capitalização composta dos retornos diários disponíveis.
# Ela não representa o ROI de uma posição ao longo de todo o calendário.
#
# Muitos itens têm mediana exatamente igual a zero, pois o preço de 24 horas frequentemente se repete.
# A curva suaviza essa concentração.

# %%
item_measures = calculate_item_measures(prices)

measure_densities = estimate_measure_densities(item_measures)

MEASURE_TITLES = {
    "mean_return": "Média aritmética dos retornos diários",
    "median_return": "Mediana dos retornos diários",
    "std_return": "Desvio-padrão dos retornos diários",
    "geometric_return": "Média geométrica dos retornos diários",
}

charts["item_distributions"] = (
    alt.Chart(measure_densities.with_columns(pl.col("measure").replace_strict(MEASURE_TITLES, return_dtype=pl.String)))
    .mark_area(
        color="black",
        fillOpacity=notebook_parameters.density_opacity,
        interpolate="monotone",
        line=alt.OverlayMarkDef(color="black"),
    )
    .encode(
        x=alt.X("value:Q", title=None, axis=alt.Axis(format="%")),
        y=alt.Y("density:Q", title="Densidade"),
    )
    .properties(width=notebook_parameters.density_width, height=notebook_parameters.density_height)
    .facet(
        facet=alt.Facet("measure:N", title=None, sort=list(MEASURE_TITLES.values())),
        columns=notebook_parameters.density_columns,
    )
    .resolve_scale(x="independent", y="independent")
    .properties(config=CHART_CONFIG)
)

# %% [markdown]
# **Distribuição das medidas de retorno entre os itens**

# %% jupyter={"source_hidden": true}
charts["item_distributions"]

# %% [markdown]
# ## Retornos por raridade e por faixa de preço
#
# As tabelas descrevem diferenças de retorno e risco entre raridades e faixas de preço. Glaus (2022) encontra
# um padrão de promoção mais forte entre itens comuns.
#
# Guede-Fernández et al. (2025) relacionam raridade e liquidez. Um item pode aparecer em mais de uma faixa,
# pois seu preço varia ao longo do período.

# %%
rarity = summarize_segments(prices, build_rarity_segment())

tables["rarity"] = build_segment_table(
    rarity,
    "Raridade",
    "DP: desvio padrão. Ordem pelo preço mediano. Os tipos de item usam escalas de raridade diferentes.",
)

# %% [markdown]
# **Retornos diários por raridade — CS:GO**

# %% jupyter={"source_hidden": true}
tables["rarity"]

# %%
price_buckets = summarize_segments(prices, build_price_segment())

tables["price_buckets"] = build_segment_table(
    price_buckets,
    "Preço diário (US$)",
    "DP: desvio padrão. Um item entra em mais de uma faixa quando o preço cruza a fronteira.",
)

# %% [markdown]
# **Retornos diários por faixa de preço — CS:GO**

# %% jupyter={"source_hidden": true}
tables["price_buckets"]

# %% jupyter={"source_hidden": true, "outputs_hidden": true}
write_outputs(tables, charts, tables_path, images_path)
