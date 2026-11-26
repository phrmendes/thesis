# %% [markdown]
# # Qualidade e disponibilidade dos preços dos itens de CS:GO
#
# Este notebook descreve os dados e os efeitos dos filtros de limpeza. A análise apresenta a disponibilidade
# dos preços, o histórico de cada item e os critérios de seleção.
#
# Também examina grandes variações de preço e compara as medidas disponíveis nas diferentes fontes.

# %% jupyter={"source_hidden": true}
import altair as alt
import polars as pl
from great_tables import GT, md
from great_tables.vals import fmt_integer, fmt_number, fmt_percent
from helpers.activity import summarize_activity
from helpers.audit import calculate_audit_metrics
from helpers.coverage import (
    calculate_coverage_by_day,
    calculate_quality_metrics,
    group_launch_periods,
    summarize_coverage_daily,
    summarize_coverage_items,
)
from helpers.export import enable_inline_table_styles, write_outputs
from helpers.formatting import (
    DATE_FORMAT,
    FONT_FAMILY,
    HELPER_PARAMETERS,
    LOCALE,
    TABLE_SOURCE,
    build_cap_text,
    build_metric_table,
)
from helpers.jumps import find_jump_days, summarize_jumps
from helpers.parameters import parameters
from helpers.paths import get_repo_root
from helpers.schemas import read_table
from helpers.sources import compare_sources

alt.renderers.enable("png", embed_options={"formatLocale": LOCALE, "timeFormatLocale": LOCALE})

CHART_CONFIG = alt.Config(
    font=FONT_FAMILY,
    title=alt.TitleConfig(anchor=HELPER_PARAMETERS.title_anchor, align=HELPER_PARAMETERS.title_align),
    legend=alt.LegendConfig(orient=HELPER_PARAMETERS.legend_orient),
)

enable_inline_table_styles()

notebook_parameters = parameters().data_quality

paths = parameters().paths

prices_path = get_repo_root() / paths.prices

assets_path = get_repo_root() / paths.assets

audit_path = get_repo_root() / paths.audit

tables_path = get_repo_root() / paths.tables

images_path = get_repo_root() / paths.images

reversal_lower_label = pl.select(
    fmt_percent(pl.lit(notebook_parameters.reversal_range[0]), decimals=0, locale=LOCALE)
).item()

reversal_upper_label = pl.select(
    fmt_percent(pl.lit(notebook_parameters.reversal_range[1]), decimals=0, locale=LOCALE)
).item()

reversal_description = (
    f"O preço observado após o salto fica entre {reversal_lower_label} e "
    f"{reversal_upper_label} do preço anterior ao salto."
)

tables: dict[str, GT] = {}

charts: dict[str, alt.TopLevelMixin] = {}

TOP_JUMP_DAYS = notebook_parameters.top_jump_days

CAP_TEXT = build_cap_text()

CLEAN_PARAMETERS = parameters().clean

cheap_price_label = pl.select(
    fmt_number(pl.lit(notebook_parameters.cheap_price), decimals=2, drop_trailing_zeros=True, locale=LOCALE)
).item()

AUDIT_LABELS = {
    "raw_rows": "Registros nos dados brutos",
    "raw_assets": "Itens nos dados brutos",
    "snapshot_days": "Dias com preços positivos",
    "dropped_days": "Dias excluídos por baixa cobertura (1)",
    "daily_rows": "Registros com preço positivo em dias aproveitados",
    "daily_assets": "Itens com preço positivo em dias aproveitados",
    "selected_assets": "Itens selecionados com dados de treinamento",
    "selected_daily_rows": "Registros dos itens selecionados",
    "valid_rows": "Registros dentro dos limites de preço",
    "bounds_removed_rows": "Registros excluídos pelos limites de preço",
    "valid_assets": "Itens com preços dentro dos limites",
    "cleaned_rows": "Registros após a limpeza",
    "unchanged_daily_share": "Parcela de preços iguais aos da observação anterior",
    "longest_unchanged_run": "Maior sequência de preços iguais (dias observados)",
    f"assets_with_run_over_{CLEAN_PARAMETERS.max_unchanged_days}_days": (
        f"Itens com preços iguais por mais de {CLEAN_PARAMETERS.max_unchanged_days} dias observados"
    ),
    "rows_without_return_share": "Parcela de registros sem retorno",
    "daily_jumps": "Saltos de preço (2)",
    "reversed_jumps": "Saltos seguidos de reversão (3)",
    "capped_returns": f"Retornos no teto de {CAP_TEXT}",
    "assets_below_one": f"Itens com preço médio inferior a US$ {cheap_price_label}",
    "missing_rarity_share": "Registros sem informação de raridade",
}


DAILY_LABELS = {
    "first_price_day": "Primeiro dia com preço",
    "first_return_day": "Primeiro dia com retorno",
    "last_price_day": "Último dia com preço",
    "price_days": "Dias com preço",
    "return_row_share": "Parcela de registros com retorno",
    "min_assets_per_day": "Mínimo de itens por dia",
    "avg_assets_per_day": "Média de itens por dia",
    "max_assets_per_day": "Máximo de itens por dia",
}


INTEGER_SELECTION_COLUMNS = [
    "assets",
    "selected",
    "low_price",
    "few_observations",
    "no_training_data",
]

METRIC_LABELS = {
    "records": "Registros",
    "assets": "Itens distintos",
    "days": "Dias distintos",
    "min_days_per_asset": "Mínimo de dias por item",
    "avg_days_per_asset": "Média de dias por item",
    "max_days_per_asset": "Máximo de dias por item",
    "positive_return_days": "Dias com retorno positivo",
    "negative_return_days": "Dias com retorno negativo",
    "zero_return_days": "Dias com retorno zero",
    "days_without_return": "Registros sem retorno",
}


up_jump_label = pl.select(fmt_percent(pl.lit(notebook_parameters.up_jump), decimals=0, locale=LOCALE)).item()

down_jump_label = pl.select(fmt_percent(pl.lit(abs(notebook_parameters.down_jump)), decimals=0, locale=LOCALE)).item()

DIRECTION_LABELS = {
    "up": f"Alta superior a {up_jump_label}",
    "down": f"Queda superior a {down_jump_label}",
}

expensive_price_label = pl.select(
    fmt_number(pl.lit(HELPER_PARAMETERS.expensive_price), decimals=2, drop_trailing_zeros=True, locale=LOCALE)
).item()

SOURCE_LABELS = {
    "steam_7d": "Média Steam de 7 dias (1)",
    "composite": "Índice csgotrader — amostra completa (2)",
    "composite_800": f"Índice csgotrader — Steam ≥ US$ {expensive_price_label} (2)",
    "buff": "BUFF (menor preço anunciado)",
}

prices = read_table("prices", prices_path)

assets = read_table("assets", assets_path)

# %% [markdown]
# ## Auditoria da limpeza
#
# A auditoria mostra quantos registros e itens permanecem após cada etapa da limpeza. A tabela também resume
# preços repetidos, retornos ausentes e grandes variações de preço.

# %%
audit = calculate_audit_metrics(read_table("audit", audit_path), prices)

audit_values = audit.select(*AUDIT_LABELS).select(
    fmt_integer(
        pl.exclude("unchanged_daily_share", "rows_without_return_share", "missing_rarity_share"), locale=LOCALE
    ),
    fmt_percent(
        pl.col("unchanged_daily_share", "rows_without_return_share", "missing_rarity_share"), decimals=2, locale=LOCALE
    ),
)

tables["audit"] = (
    GT(build_metric_table(audit_values, AUDIT_LABELS), locale=LOCALE)
    .tab_source_note(TABLE_SOURCE)
    .tab_source_note(
        "Registros e itens que permanecem após cada etapa da limpeza. "
        "O preço é a média das vendas na Steam nas últimas 24 horas."
    )
    .cols_label(metric_name=md("**Métrica**"), metric_value=md("**Valor**"))
    .tab_source_note(
        "(1) A limpeza compara o número de preços positivos de cada dia com a mediana desse número na amostra. "
        f"O dia fica fora da análise quando esse número não atinge {CLEAN_PARAMETERS.min_day_share:.0%} da mediana."
    )
    .tab_source_note(f"(2) O preço aumenta mais de {up_jump_label} ou diminui mais de {down_jump_label}.")
    .tab_source_note(f"(3) {reversal_description}")
)

# %% [markdown]
# **Auditoria da limpeza dos dados — CS:GO**

# %% jupyter={"source_hidden": true}
tables["audit"]

# %% [markdown]
# ## Disponibilidade de preços ao longo do período
#
# A tabela informa as datas disponíveis e quantos itens têm preço em cada dia. O gráfico mostra como essa
# quantidade varia ao longo do período.
#
# Quedas bruscas sinalizam dias com menos dados e ajudam a identificar possíveis falhas na coleta.

# %%
coverage = summarize_coverage_daily(prices, audit)

coverage_values = coverage.select(
    pl.col("first_price_day", "first_return_day", "last_price_day").dt.strftime(DATE_FORMAT),
    fmt_integer(pl.col("price_days", "min_assets_per_day", "max_assets_per_day"), locale=LOCALE),
    fmt_number(pl.col("avg_assets_per_day"), decimals=0, locale=LOCALE),
    fmt_percent(pl.col("return_row_share"), decimals=2, locale=LOCALE),
)

tables["coverage_daily"] = (
    GT(build_metric_table(coverage_values, DAILY_LABELS), locale=LOCALE)
    .tab_source_note(TABLE_SOURCE)
    .cols_label(metric_name=md("**Métrica**"), metric_value=md("**Valor**"))
)

# %% [markdown]
# **Cobertura temporal — CS:GO**

# %% jupyter={"source_hidden": true}
tables["coverage_daily"]

# %%
charts["coverage"] = (
    alt.Chart(calculate_coverage_by_day(prices))
    .mark_line(color="black")
    .encode(x=alt.X("date:T", title="Dia"), y=alt.Y("assets:Q", title="Itens com preço"))
    .properties(width=HELPER_PARAMETERS.chart_width, height=HELPER_PARAMETERS.chart_height)
    .properties(config=CHART_CONFIG)
)

# %% [markdown]
# **Ativos com preço em cada dia**

# %% jupyter={"source_hidden": true}
charts["coverage"]

# %% [markdown]
# ## Quantidade de dias com preço por item
#
# A tabela agrupa os itens pelo número de dias com preço observado. Em cada grupo, apresenta o total de itens
# e quantos passam pelos filtros de seleção.

# %%
price_history = summarize_coverage_items(assets)

tables["coverage_items"] = (
    GT(price_history, locale=LOCALE)
    .tab_source_note(TABLE_SOURCE)
    .cols_align("left", columns="days_range")
    .fmt_integer(columns=["universe_assets", "selected_assets"])
    .cols_label(
        days_range=md("**Dias com preço**"),
        universe_assets=md("**Universo de itens** (1)"),
        selected_assets=md("**Itens selecionados** (2)"),
    )
    .tab_source_note("(1) O universo conta todos os itens com preço positivo.")
    .tab_source_note("(2) A seleção usa só os dias de treinamento.")
)

# %% [markdown]
# **Histórico de preços dos itens — CS:GO**

# %% jupyter={"source_hidden": true}
tables["coverage_items"]

# %% [markdown]
# ## Seleção por semestre do primeiro registro
#
# A tabela agrupa os itens pelo semestre do primeiro registro de preço positivo na base de dados.
# O primeiro registro indica quando o preço aparece nos dados, não quando o item chega ao mercado.
# As colunas mostram quantos itens passam pelos filtros de treinamento e os motivos de exclusão dos demais.

# %%
selection = (
    group_launch_periods(assets)
    .with_columns(pl.col("launch_period").cast(pl.String).str.replace(r"^(\d{4})-H(\d)$", "${2}º sem. ${1}"))
    .select("launch_period", "assets", "selected", "no_training_data", "few_observations", "low_price")
)

min_mean_price_label = pl.select(
    fmt_number(pl.lit(CLEAN_PARAMETERS.min_mean_price), decimals=2, drop_trailing_zeros=True, locale=LOCALE)
).item()

tables["selection"] = (
    GT(selection, locale=LOCALE)
    .tab_options(table_font_size="9.5pt")
    .tab_source_note(TABLE_SOURCE)
    .tab_source_note(
        "A classificação considera o primeiro motivo de exclusão aplicável, da esquerda para a direita. "
        "Itens sem motivo de exclusão entram em Selecionados. "
        "Em cada linha, selecionados e excluídos somam o total de itens."
    )
    .cols_align("left", columns="launch_period")
    .fmt_integer(columns=INTEGER_SELECTION_COLUMNS)
    .tab_spanner(label=md("**Excluídos, por motivo**"), columns=["no_training_data", "few_observations", "low_price"])
    .cols_label(
        launch_period=md("**Semestre** (1)"),
        assets=md("**Total**"),
        selected=md("**Selecionados**"),
        no_training_data=md("**Sem treinamento**"),
        few_observations=md("**Histórico curto** (2)"),
        low_price=md("**Preço baixo** (3)"),
    )
    .tab_source_note(
        "(1) O primeiro registro corresponde à primeira data com preço positivo na base. "
        "Não indica o lançamento do item."
    )
    .tab_source_note(f"(2) Menos de {CLEAN_PARAMETERS.min_observations} dias com preço no período de treinamento.")
    .tab_source_note(f"(3) Preço médio nos dias de treinamento inferior a US$ {min_mean_price_label}.")
)

# %% [markdown]
# **Itens selecionados e excluídos por semestre do primeiro registro — CS:GO**

# %% jupyter={"source_hidden": true}
tables["selection"]

# %% [markdown]
# Nenhum item com primeiro registro de preço a partir de 2022 entra na seleção atual.
# O requisito de observações no treinamento concentra a amostra em itens com registros mais antigos.

# %% [markdown]
# ## Amostra de preços e retornos

# %%
quality = calculate_quality_metrics(prices)

quality_values = quality.select(
    fmt_integer(pl.exclude("avg_days_per_asset"), locale=LOCALE),
    fmt_number(pl.col("avg_days_per_asset"), decimals=1, locale=LOCALE),
)

tables["quality"] = (
    GT(build_metric_table(quality_values, METRIC_LABELS), locale=LOCALE)
    .tab_source_note(TABLE_SOURCE)
    .cols_label(metric_name=md("**Métrica**"), metric_value=md("**Valor**"))
)

# %% [markdown]
# **Qualidade do conjunto de dados limpo — CS:GO**

# %% jupyter={"source_hidden": true}
tables["quality"]

# %% [markdown]
# ## Saltos de preço e reversões
#
# Os saltos correspondem a variações que ultrapassam os limites definidos nos parâmetros,
# entre observações consecutivas.
#
# A primeira tabela mostra quantos desses saltos apresentam reversão na observação seguinte. A segunda lista
# os dias com maior concentração de saltos.

# %%
jumps = summarize_jumps(prices).with_columns(
    pl.col("direction").replace_strict(DIRECTION_LABELS, return_dtype=pl.String)
)

tables["jumps"] = (
    GT(jumps, locale=LOCALE)
    .tab_options(table_font_size="10.5pt")
    .tab_source_note(TABLE_SOURCE)
    .cols_align("left", columns="direction")
    .fmt_integer(columns=["jumps"])
    .fmt_percent(columns=["reversed_share", "training_share"], decimals=1)
    .fmt_percent(columns=["median_size"], decimals=0)
    .cols_label(
        direction=md("**Direção**"),
        jumps=md("**Saltos**"),
        reversed_share=md("**Revertidos** (1)"),
        median_size=md("**Tamanho mediano** (2)"),
        training_share=md("**No treinamento**"),
    )
    .tab_source_note(f"(1) {reversal_description}")
    .tab_source_note("(2) Variação do preço em módulo.")
)

# %% [markdown]
# **Saltos de preço — CS:GO**

# %% jupyter={"source_hidden": true}
tables["jumps"]

# %%
days = find_jump_days(prices, TOP_JUMP_DAYS).with_columns(pl.col("date").dt.strftime(DATE_FORMAT))

tables["jump_days"] = (
    GT(days, locale=LOCALE)
    .tab_source_note(TABLE_SOURCE)
    .tab_source_note(f"Os {TOP_JUMP_DAYS} dias com mais saltos.")
    .fmt_integer(columns=["jumps", "items"])
    .fmt_percent(columns=["jump_share"], decimals=1)
    .cols_label(
        date=md("**Dia**"),
        jumps=md("**Saltos**"),
        items=md("**Itens com retorno**"),
        jump_share=md("**Itens que saltaram** (1)"),
    )
    .tab_source_note("(1) Parcela dos itens com retorno no dia.")
)

# %% [markdown]
# **Dias com mais saltos de preço — CS:GO**

# %% jupyter={"source_hidden": true}
tables["jump_days"]

# %% [markdown]
# ## Frequência de preços observados por item
#
# A tabela agrupa os itens pela parcela de dias com preço observado entre o primeiro e o último registro.
#
# Essa parcela descreve a frequência dos preços disponíveis. Ela não informa a quantidade de unidades vendidas
# nem o volume financeiro negociado.

# %%
activity = summarize_activity(prices)

tables["activity"] = (
    GT(activity, locale=LOCALE)
    .tab_source_note(TABLE_SOURCE)
    .tab_source_note(
        "Parcela dos dias com preço de 24 horas entre o primeiro e o último registro do item. "
        "Essa medida descreve a disponibilidade de preços, não o volume negociado."
    )
    .cols_align("left", columns="share_bucket")
    .fmt_integer(columns=["items"])
    .cols_label(share_bucket=md("**Dias com preço de 24 horas**"), items=md("**Itens**"))
)

# %% [markdown]
# **Parcela de dias com preço por item — CS:GO**

# %% jupyter={"source_hidden": true}
tables["activity"]

# %% [markdown]
# ## Preço Steam de 24 horas e outras referências
#
# A tabela compara o preço médio de 24 horas da Steam com a média de 7 dias, o índice csgotrader e os anúncios
# da BUFF. Ela mostra a disponibilidade dos dados, a relação entre os valores e a correlação entre suas variações.
# Essa comparação não verifica se os resultados das regressões e da carteira se mantêm com outra referência.

# %%
sources = compare_sources(prices).with_columns(pl.col("source").replace_strict(SOURCE_LABELS, return_dtype=pl.String))

tables["sources"] = (
    GT(sources, locale=LOCALE)
    .tab_options(table_font_size="9pt")
    .tab_source_note(TABLE_SOURCE)
    .tab_source_note(
        "A disponibilidade é a parcela das observações que também contêm um valor na referência. "
        "Essa parcela considera apenas as observações com preço Steam de 24 horas. "
        "Não é uma contagem de dias distintos. "
        "A razão compara os valores do mesmo item e dia. Valores acima de 1 indicam preço Steam superior à referência. "
        "Cada observação pareada compara variações percentuais do mesmo item em dias consecutivos. "
        f"As variações têm limite de {CAP_TEXT}."
    )
    .fmt_percent(columns=["day_share"], decimals=1)
    .fmt_number(columns=["median_ratio", "return_correlation"], decimals=2)
    .fmt_integer(columns=["pairs"])
    .cols_label(
        source=md("**Referência**"),
        day_share=md("**Disponibilidade**"),
        median_ratio=md("**Razão mediana**"),
        return_correlation=md("**Correlação**"),
        pairs=md("**Pares**"),
    )
    .tab_source_note(
        "(1) A média de 7 dias usa períodos sobrepostos. Suas variações não equivalem aos retornos diários de preços."
    )
    .tab_source_note("(2) O índice csgotrader é uma medida composta do autor, não um preço de venda.")
)

# %% [markdown]
# **Preço Steam de 24 horas e referências alternativas — CS:GO**

# %% jupyter={"source_hidden": true}
tables["sources"]

# %% jupyter={"source_hidden": true, "outputs_hidden": true}
write_outputs(tables, charts, tables_path, images_path)
