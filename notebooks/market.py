# %% [markdown]
# # Evolução do mercado e dependência dos retornos — CS:GO
#
# O notebook descreve o mercado com base no painel de preços dos itens. A análise mostra o índice de mercado,
# a volatilidade e a dependência dos retornos dentro dos itens e em relação ao mercado.

# %% jupyter={"source_hidden": true}
import altair as alt
import polars as pl
from great_tables import GT, md
from great_tables.vals import fmt_number, fmt_percent
from helpers.export import enable_inline_table_styles, write_outputs
from helpers.formatting import FONT_FAMILY, HELPER_PARAMETERS, LOCALE, TABLE_SOURCE, build_metric_table
from helpers.market import LAGS, add_market_volatility, get_market_series, summarize_market_dynamics
from helpers.parameters import parameters
from helpers.paths import get_repo_root
from helpers.schemas import read_table
from msgspec import to_builtins

alt.renderers.enable("png", embed_options={"formatLocale": LOCALE, "timeFormatLocale": LOCALE})

CHART_CONFIG = alt.Config(
    font=FONT_FAMILY,
    title=alt.TitleConfig(anchor=HELPER_PARAMETERS.title_anchor, align=HELPER_PARAMETERS.title_align),
    legend=alt.LegendConfig(orient=HELPER_PARAMETERS.legend_orient),
)

enable_inline_table_styles()

notebook_parameters = parameters().market

paths = parameters().paths

prices_path = get_repo_root() / paths.prices

tables_path = get_repo_root() / paths.tables

images_path = get_repo_root() / paths.images

tables: dict[str, GT] = {}

charts: dict[str, alt.TopLevelMixin] = {}

DYNAMICS_LABELS = {
    "mean_return": "Retorno diário médio do mercado",
    "std_return": "Desvio padrão do retorno do mercado",
    **{f"market_lag_{lag}": f"Autocorrelação do mercado (defasagem {lag})" for lag in LAGS},
    **{f"asset_lag_{lag}": f"Autocorrelação dentro dos itens (defasagem {lag})" for lag in LAGS},
    "mean_market_correlation": "Correlação média dos itens com o mercado (1)",
    "median_market_correlation": "Correlação mediana dos itens com o mercado (1)",
}


prices = read_table("prices", prices_path)

event_name = pl.col("name").replace({"CS2 announcement": "Anúncio do CS2", "CS2 release": "Lançamento do CS2"})

event_frame = pl.DataFrame(to_builtins(notebook_parameters.events)).with_columns(
    pl.col("date").str.to_date(), event_name
)

line_styles = alt.Scale(
    domain=["Índice de mercado", "Volatilidade móvel", "Anúncio do CS2", "Lançamento do CS2"],
    range=notebook_parameters.line_styles,
)

event_rules = (
    alt.Chart(event_frame)
    .mark_rule(color="black")
    .encode(x="date:T", strokeDash=alt.StrokeDash("name:N", title="Série ou evento", scale=line_styles))
)

volatility_title = f"Desvio padrão ({notebook_parameters.volatility_days} observações)"

# %% [markdown]
# ## Evolução do índice de mercado e da volatilidade
#
# A linha contínua do painel superior mostra o índice de mercado. A do painel inferior mostra a volatilidade móvel.
# As linhas verticais marcam o anúncio e o lançamento do CS2. A legenda distingue os eventos pelos padrões de traço.
#
# A escala logarítmica representa variações percentuais iguais por distâncias iguais no eixo vertical. O
# índice acumula a média dos retornos logarítmicos, em vez da média aritmética dos retornos simples.

# %%
market = get_market_series(prices)

market_daily = add_market_volatility(market)

index_line = (
    alt.Chart(market_daily)
    .transform_calculate(series="'Índice de mercado'")
    .mark_line(color="black")
    .encode(
        x=alt.X("date:T", title="Dia"),
        y=alt.Y("index:Q", title="Índice (início = 1)", scale=alt.Scale(type="log", zero=False, nice=False)),
        strokeDash=alt.StrokeDash("series:N", title="Série ou evento", scale=line_styles),
    )
)

volatility_line = (
    alt.Chart(market_daily)
    .transform_calculate(series="'Volatilidade móvel'")
    .mark_line(color="black")
    .encode(
        x=alt.X("date:T", title="Dia"),
        y=alt.Y("volatility:Q", title=volatility_title),
        strokeDash=alt.StrokeDash("series:N", title="Série ou evento", scale=line_styles),
    )
)

charts["market"] = alt.vconcat(
    (index_line + event_rules).properties(
        width=HELPER_PARAMETERS.chart_width, height=notebook_parameters.index_height, title="Índice de mercado"
    ),
    (volatility_line + event_rules).properties(
        width=HELPER_PARAMETERS.chart_width,
        height=notebook_parameters.volatility_height,
        title="Volatilidade do retorno médio diário",
    ),
).properties(config=CHART_CONFIG)

# %% [markdown]
# **Índice do mercado e volatilidade móvel**

# %% jupyter={"source_hidden": true}
charts["market"]

# %% [markdown]
# ## Dependência dos retornos no painel
#
# A autocorrelação descreve a associação dos retornos com observações anteriores. A correlação entre cada
# item e o mercado mostra quanto seus retornos variam em conjunto.
#
# As defasagens do mercado contam observações disponíveis. Dentro dos itens, só entram pares cuja diferença
# de datas coincide com a defasagem.

# %%
dynamics = summarize_market_dynamics(prices, market)

dynamics_values = dynamics.select(
    fmt_percent(pl.col("mean_return", "std_return"), decimals=2, locale=LOCALE),
    fmt_number(pl.exclude("mean_return", "std_return"), decimals=4, locale=LOCALE),
)

tables["dynamics"] = (
    GT(build_metric_table(dynamics_values, DYNAMICS_LABELS), locale=LOCALE)
    .tab_source_note(TABLE_SOURCE)
    .tab_source_note(
        "Retorno de mercado: média simples dos retornos diários limitados. Desvio padrão amostral. "
        "As correlações descrevem associações lineares entre os retornos."
    )
    .cols_label(metric_name=md("**Métrica**"), metric_value=md("**Valor**"))
    .tab_source_note(f"(1) Itens com pelo menos {HELPER_PARAMETERS.item_min_days} dias com retorno observado.")
)

# %% [markdown]
# **Retornos e dependência no mercado — CS:GO**

# %% jupyter={"source_hidden": true}
tables["dynamics"]

# %% [markdown]
# Os retornos do mercado apresentam autocorrelação positiva nas quatro defasagens analisadas.
# Dentro dos itens, a autocorrelação negativa na primeira defasagem indica reversão de curto prazo.
# Nas demais defasagens, a autocorrelação fica próxima de zero.
# As correlações média e mediana dos itens com o mercado indicam fraca associação linear.

# %% jupyter={"source_hidden": true, "outputs_hidden": true}
write_outputs(tables, charts, tables_path, images_path)
