# %% [markdown]
# # Análise exploratória dos preços de itens CS:GO
#
# Lê os preços semanais limpos, audita a limpeza, calcula as tabelas da EDA, mostra cada resultado
# e exporta as tabelas LaTeX e os gráficos PNG.

# %%
from argparse import ArgumentParser
from pathlib import Path

import altair as alt
import polars as pl
from great_tables import GT
from helpers.activity import activity_summary
from helpers.audit import audit_metrics
from helpers.coverage import coverage_daily, coverage_items, coverage_weekly, launch_period_groups, quality_metrics
from helpers.formatting import DEC_MARK, SEP_MARK, format_metric, metric_text_table, write_latex_table
from helpers.market import LAGS, market_dynamics, market_series, market_with_volatility
from helpers.params import load_params
from helpers.paths import repo
from helpers.returns import RETURN_COLUMNS, return_distribution, return_statistics
from helpers.runtime import notebook_arguments
from helpers.sources import source_comparison

# %% [markdown]
# ## Rótulos e formatos das tabelas

# %%
WIDE_TABLES = frozenset({"returns", "distribution", "selection", "sources"})

LABEL_MAP = {"rest": "Restante", "overall": "Geral"}

DAILY_LABELS = {
    "first_price_week": "Primeira semana com preço",
    "first_return_week": "Primeira semana com retorno",
    "last_price_day": "Último dia com preço",
    "return_weeks": "Semanas com retorno",
    "asset_week_share": "Itens-semana com preço real",
    "min_assets_per_week": "Mín. ativos/semana",
    "avg_assets_per_week": "Média ativos/semana",
    "max_assets_per_week": "Máx. ativos/semana",
}

DAILY_FORMATS = {
    "first_price_week": "%d/%m/%Y",
    "first_return_week": "%d/%m/%Y",
    "last_price_day": "%d/%m/%Y",
    "return_weeks": "d",
    "asset_week_share": ".2%",
    "min_assets_per_week": "d",
    "avg_assets_per_week": ".0f",
    "max_assets_per_week": "d",
}

METRIC_LABELS = {
    "records": "Registros",
    "assets": "Ativos distintos",
    "weeks": "Semanas distintas",
    "min_weeks_per_asset": "Mín. semanas/ativo",
    "avg_weeks_per_asset": "Média semanas/ativo",
    "max_weeks_per_asset": "Máx. semanas/ativo",
    "positive_return_weeks": "Semanas com retorno positivo",
    "negative_return_weeks": "Semanas com retorno negativo",
    "zero_return_weeks": "Semanas com retorno zero",
    "filled_rows": "Registros preenchidos",
}

METRIC_FORMATS = {
    "records": "d",
    "assets": "d",
    "weeks": "d",
    "min_weeks_per_asset": "d",
    "avg_weeks_per_asset": ".1f",
    "max_weeks_per_asset": "d",
    "positive_return_weeks": "d",
    "negative_return_weeks": "d",
    "zero_return_weeks": "d",
    "filled_rows": "d",
}

DYNAMICS_LABELS = {
    "market_mean_return": "Retorno semanal médio do mercado",
    "market_std_return": "Desvio padrão do retorno do mercado",
    **{f"market_lag_{lag}": f"Autocorrelação do mercado (defasagem {lag})" for lag in LAGS},
    **{f"asset_lag_{lag}": f"Autocorrelação dentro dos itens (defasagem {lag})" for lag in LAGS},
    "mean_market_correlation": "Correlação média dos itens com o mercado",
    "median_market_correlation": "Correlação mediana dos itens com o mercado",
}

DYNAMICS_FORMATS = {
    "market_mean_return": ".2%",
    "market_std_return": ".2%",
    **{f"market_lag_{lag}": ".4f" for lag in LAGS},
    **{f"asset_lag_{lag}": ".4f" for lag in LAGS},
    "mean_market_correlation": ".4f",
    "median_market_correlation": ".4f",
}

DISTRIBUTION_LABELS = {"capped": "Limitado (±100%)", "raw": "Bruto"}

SOURCE_LABELS = {
    "composite": "Índice csgotrader (todos os itens)",
    "composite_800": "Índice csgotrader (preço ≥ US$ 800)",
    "buff": "BUFF (menor oferta)",
}

PERCENT_COLUMNS = ["mean", "std", "p01", "p05", "p50", "p95", "p99", "share_above_half"]

INTEGER_SELECTION_COLUMNS = [
    "assets",
    "selected",
    "low_price",
    "few_observations",
    "no_training_data",
]


# %% [markdown]
# ## Argumentos da linha de comando

# %%
parser = ArgumentParser(description="EDA: calcula, mostra e exporta as tabelas e os gráficos.")
parser.add_argument("--prices", type=Path, default=repo() / "files/prices.parquet", help="Preços semanais limpos.")
parser.add_argument("--assets", type=Path, default=repo() / "files/assets.parquet", help="Universo de ativos.")
parser.add_argument("--audit", type=Path, default=repo() / "files/audit.parquet", help="Diagnóstico da limpeza.")
parser.add_argument("--tables", type=Path, default=repo() / "tex/tables", help="Pasta para os arquivos LaTeX.")
parser.add_argument("--images", type=Path, default=repo() / "images", help="Pasta para os gráficos.")
args = parser.parse_args(notebook_arguments())

# %% [markdown]
# ## Carregar dados e auditar a limpeza

# %%
prices = pl.read_parquet(args.prices)
assets = pl.read_parquet(args.assets)
audit = audit_metrics(pl.read_parquet(args.audit), prices)
audit

# %% [markdown]
# ## Analisar cobertura, seleção e qualidade dos dados

# %%
coverage = coverage_daily(prices, audit)
coverage

# %%
persistence = coverage_items(assets)
persistence

# %%
groups = launch_period_groups(assets)
groups

# %%
quality = quality_metrics(prices)
quality

# %% [markdown]
# ## Analisar retornos, distribuição e dinâmica do mercado

# %%
returns = return_statistics(prices)
returns

# %%
distribution = return_distribution(prices)
distribution

# %%
market = market_series(prices)
market

# %%
dynamics = market_dynamics(prices, market)
dynamics

# %% [markdown]
# ## Comparar fontes de preço e atividade de mercado

# %%
sources = source_comparison(prices)
sources

# %%
activity = activity_summary(prices)
activity

# %% [markdown]
# ## Construir tabelas para a tese

# %% [markdown]
# ### Cobertura temporal dos preços

# %%
coverage_text = metric_text_table(coverage, DAILY_LABELS, DAILY_FORMATS)

coverage_gt = (
    GT(coverage_text)
    .tab_header(title="Cobertura Temporal — CS:GO")
    .cols_label(metric_name="Métrica", metric_value="Valor")
)
coverage_gt

# %% [markdown]
# ### Persistência dos itens no conjunto de dados

# %%
persistence_gt = (
    GT(persistence)
    .tab_header(title="Persistência dos Itens — CS:GO")
    .fmt_integer(columns=["universe_assets", "selected_assets"], sep_mark=SEP_MARK)
    .cols_label(
        weeks_range="Semanas com preço",
        universe_assets="Itens (universo)",
        selected_assets="Itens selecionados",
    )
    .tab_source_note("O universo conta todos os itens com preço positivo. A seleção usa só as semanas de treino.")
)
persistence_gt

# %% [markdown]
# ### Seleção dos itens por primeira observação

# %%
groups_gt = (
    GT(groups)
    .tab_header(title="Seleção dos Itens por Primeira Observação — CS:GO")
    .fmt_integer(columns=INTEGER_SELECTION_COLUMNS, sep_mark=SEP_MARK)
    .cols_label(
        launch_period="Primeira observação",
        assets="Itens",
        selected="Selecionados",
        low_price="Preço médio abaixo de US$ 1",
        few_observations="Poucas observações",
        no_training_data="Sem dados no treino",
    )
    .tab_source_note(
        "Primeira observação: semestre em que o item aparece pela primeira vez. "
        "O primeiro grupo inclui itens anteriores à coleta. "
        "Cada item recebe um só motivo, na ordem: sem dados no treino, poucas observações, "
        "preço médio baixo."
    )
)
groups_gt

# %% [markdown]
# ### Qualidade do conjunto de dados limpo

# %%
quality_text = metric_text_table(quality, METRIC_LABELS, METRIC_FORMATS)

quality_gt = (
    GT(quality_text)
    .tab_header(title="Qualidade do Conjunto de Dados Limpo — CS:GO")
    .cols_label(metric_name="Métrica", metric_value="Valor")
)
quality_gt

# %% [markdown]
# ### Estatísticas dos retornos semanais

# %%
returns_text = returns.with_columns(pl.col("name").replace(LABEL_MAP))
asset_rows = list(range(returns_text.height - 2))
pooled_rows = [returns_text.height - 2, returns_text.height - 1]

returns_gt = (
    GT(returns_text)
    .tab_header(title="Estatísticas dos Retornos — Itens CS:GO")
    .fmt_percent(columns=RETURN_COLUMNS, decimals=2, sep_mark=SEP_MARK, dec_mark=DEC_MARK)
    .fmt_number(columns=["n_weeks"], rows=asset_rows, decimals=0, sep_mark=SEP_MARK, dec_mark=DEC_MARK)
    .fmt_number(columns=["n_weeks"], rows=pooled_rows, decimals=1, sep_mark=SEP_MARK, dec_mark=DEC_MARK)
    .fmt_number(columns=["sharpe", "sortino"], decimals=2, sep_mark=SEP_MARK, dec_mark=DEC_MARK)
    .tab_spanner(label="Retornos", columns=RETURN_COLUMNS)
    .cols_label(
        name="Item",
        mean_return="Média",
        median_return="Mediana",
        min_return="Mínimo",
        max_return="Máximo",
        std_return="DP",
        negative_returns_std="DP (negativos)",
        n_weeks="Semanas",
        sharpe="Sharpe",
        sortino="Sortino",
    )
    .cols_hide("rank_n")
    .tab_source_note(
        "DP: desvio padrão. Razões semanais com taxa livre de risco zero. "
        "Sharpe: média sobre o DP dos retornos. Sortino: média sobre o DP das semanas negativas. "
        "Retornos limitados em ±100%. Ranking entre itens com 100 semanas ou mais. "
        "Restante e Geral reúnem todos os retornos semanais dos itens."
    )
)
returns_gt

# %% [markdown]
# ### Distribuição dos retornos semanais

# %%
distribution_text = distribution.with_columns(pl.col("label").replace(DISTRIBUTION_LABELS))

distribution_gt = (
    GT(distribution_text)
    .tab_header(title="Distribuição dos Retornos Semanais — CS:GO")
    .fmt_percent(columns=PERCENT_COLUMNS, decimals=2, sep_mark=SEP_MARK, dec_mark=DEC_MARK)
    .fmt_number(columns=["skewness", "excess_kurtosis"], decimals=2, sep_mark=SEP_MARK, dec_mark=DEC_MARK)
    .fmt_integer(columns=["n"], sep_mark=SEP_MARK)
    .cols_label(
        label="Retorno",
        n="Observações",
        mean="Média",
        std="DP",
        skewness="Assimetria",
        excess_kurtosis="Curtose em excesso",
        p01="P1",
        p05="P5",
        p50="P50",
        p95="P95",
        p99="P99",
        share_above_half="|r| > 50%",
    )
    .tab_source_note(
        "DP: desvio padrão. Retornos de todos os itens reunidos. O retorno bruto não tem limite. "
        "O limite de ±100% reduz a média e o desvio padrão."
    )
)
distribution_gt

# %% [markdown]
# ### Dinâmica do mercado de itens CS:GO


# %%
def adf_text_row(label: str, statistic: float, p_value: float) -> pl.DataFrame:
    """Write one ADF test as a table row.

    Returns:
        One row with the label and the statistic with its p-value.

    """
    text = format_metric(statistic, ".2f") + f" (p = {format_metric(p_value, '.3f')})"

    return pl.DataFrame({"metric_name": [label], "metric_value": [text]})


dynamics_record = dynamics.row(0, named=True)
dynamics_text = metric_text_table(dynamics, DYNAMICS_LABELS, DYNAMICS_FORMATS)

index_test = adf_text_row(
    "Teste ADF: log do índice do mercado",
    dynamics_record["adf_index_statistic"],
    dynamics_record["adf_index_p_value"],
)

return_test = adf_text_row(
    "Teste ADF: retorno do mercado",
    dynamics_record["adf_return_statistic"],
    dynamics_record["adf_return_p_value"],
)

dynamics_gt = (
    GT(pl.concat([dynamics_text, index_test, return_test]))
    .tab_header(title="Dinâmica do Mercado — CS:GO")
    .cols_label(metric_name="Métrica", metric_value="Valor")
    .tab_source_note(
        "Mercado: média simples dos retornos semanais limitados. "
        "Correlação: itens com 100 semanas ou mais. ADF: estatística e p-valor. "
        "A autocorrelação negativa dentro dos itens pode refletir ruído no preço, não efeito de mercado."
    )
)
dynamics_gt

# %% [markdown]
# ### Comparação entre preços Steam, csgotrader e BUFF

# %%
sources_text = sources.with_columns(pl.col("source").replace(SOURCE_LABELS))

sources_gt = (
    GT(sources_text)
    .tab_header(title="Preço Steam contra Outras Fontes — CS:GO")
    .fmt_percent(columns=["week_share"], decimals=1, sep_mark=SEP_MARK, dec_mark=DEC_MARK)
    .fmt_number(columns=["median_ratio", "return_correlation"], decimals=2, sep_mark=SEP_MARK, dec_mark=DEC_MARK)
    .fmt_integer(columns=["pairs"], sep_mark=SEP_MARK)
    .cols_label(
        source="Fonte",
        week_share="Semanas com preço",
        median_ratio="Razão mediana (Steam / fonte)",
        return_correlation="Correlação dos retornos",
        pairs="Pares de semanas",
    )
    .tab_source_note(
        "Preço principal: média de vendas da Steam dos últimos 7 dias. Só semanas com preço real. "
        "Os retornos usam semanas consecutivas, limitados em ±100%. "
        "O índice csgotrader tem método próprio: média de vendas ajustada por tendência de mercado, "
        "e preço da BUFF acima de US$ 800."
    )
)
sources_gt

# %% [markdown]
# ### Atividade semanal de vendas na Steam

# %%
activity_gt = (
    GT(activity)
    .tab_header(title="Dias com Venda na Steam por Semana — CS:GO")
    .fmt_integer(columns=["item_weeks"], sep_mark=SEP_MARK)
    .cols_label(active_bucket="Dias com preço de 24 horas", item_weeks="Itens-semana")
    .tab_source_note(
        "Um dia com preço de 24 horas indica venda na Steam naquele dia. Serve como medida indireta de liquidez."
    )
)
activity_gt

# %% [markdown]
# ## Construir gráficos para a tese

# %% [markdown]
# ### Cobertura semanal do universo de ativos

# %%
coverage_weeks = coverage_weekly(prices)

coverage_figure = (
    alt.Chart(coverage_weeks)
    .mark_line()
    .encode(x=alt.X("week:T", title="Semana"), y=alt.Y("assets:Q", title="Ativos"))
    .properties(width=640, height=360)
)
coverage_figure

# %% [markdown]
# ### Índice de mercado e volatilidade móvel

# %%
chart_params = load_params()["charts"]
market_weekly = market_with_volatility(market)
event_frame = pl.DataFrame(chart_params["events"]).with_columns(pl.col("date").str.to_date())
event_rules = alt.Chart(event_frame).mark_rule(color="red", strokeDash=[4, 4]).encode(x="date:T")
volatility_title = f"Desvio padrão ({chart_params['volatility_weeks']} semanas)"

index_line = (
    alt.Chart(market_weekly)
    .mark_line()
    .encode(
        x=alt.X("week:T", title="Semana"),
        y=alt.Y("market_index:Q", title="Índice (início = 1)", scale=alt.Scale(type="log", zero=False)),
    )
)

volatility_line = (
    alt.Chart(market_weekly)
    .mark_line()
    .encode(x=alt.X("week:T", title="Semana"), y=alt.Y("volatility:Q", title=volatility_title))
)

market_figure = alt.vconcat(
    (index_line + event_rules).properties(width=640, height=220),
    (volatility_line + event_rules).properties(width=640, height=140),
)
market_figure

# %% [markdown]
# ### Histograma dos retornos semanais

# %%
bin_width = chart_params["bin_width"]
raw_returns = prices["raw_return"].clip(upper_bound=chart_params["raw_ceiling"])
return_series = {"Limitado": prices["return"], "Bruto": raw_returns}

return_bins = pl.concat(
    [
        pl.DataFrame({"retorno": series, "serie": label})
        .with_columns(((pl.col("retorno") / bin_width).floor() * bin_width).alias("faixa"))
        .group_by("serie", "faixa")
        .agg(pl.len().alias("itens_semana"))
        for label, series in return_series.items()
    ]
).sort("serie", "faixa")

returns_figure = (
    alt.Chart(return_bins)
    .mark_line(point=True, interpolate="step-after")
    .encode(
        x=alt.X("faixa:Q", title="Retorno semanal (bruto limitado em 500%)"),
        y=alt.Y("itens_semana:Q", title="Itens-semana", scale=alt.Scale(type="log")),
        color=alt.Color("serie:N", title="Retorno"),
    )
    .properties(width=640, height=360)
)
returns_figure

# %% [markdown]
# ## Exportar tabelas LaTeX e gráficos PNG

# %%
tables = {
    "coverage_daily": coverage_gt,
    "coverage_items": persistence_gt,
    "selection": groups_gt,
    "quality": quality_gt,
    "returns": returns_gt,
    "distribution": distribution_gt,
    "dynamics": dynamics_gt,
    "sources": sources_gt,
    "activity": activity_gt,
}

charts = {
    "coverage": coverage_figure,
    "market": market_figure,
    "returns_histogram": returns_figure,
}

args.tables.mkdir(parents=True, exist_ok=True)

for name, table in tables.items():
    path = args.tables / f"{name}.tex"
    write_latex_table(table, path, wide=name in WIDE_TABLES)
    print(f"Written {path}")

args.images.mkdir(parents=True, exist_ok=True)

for name, chart in charts.items():
    path = args.images / f"{name}.png"
    chart.save(path, scale_factor=2.0)
    print(f"Written {path}")
