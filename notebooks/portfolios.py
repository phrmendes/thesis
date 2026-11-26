# %% [markdown]
# # Seleção e desempenho da carteira buy-and-hold — CS:GO
#
# Este notebook avalia uma carteira que escolhe os itens com dados de treinamento e mantém as posições durante
# o período de teste.
#
# A análise compara o retorno líquido da carteira com referências simples e carteiras aleatórias. Também
# apresenta a composição da carteira e a contribuição de cada item.

# %% jupyter={"source_hidden": true}
import altair as alt
import polars as pl
from great_tables import GT, md
from great_tables.vals import fmt_integer, fmt_number, fmt_percent
from helpers.export import enable_inline_table_styles, write_outputs
from helpers.formatting import FONT_FAMILY, HELPER_PARAMETERS, LOCALE, TABLE_SOURCE, build_metric_table, wrap_chart_note
from helpers.parameters import parameters
from helpers.paths import get_repo_root
from helpers.portfolio import (
    add_selection_ratios,
    build_benchmark_paths,
    build_hold_positions,
    calculate_asset_multiples,
    calculate_item_contributions,
    calculate_portfolio_returns,
    check_thresholds,
    count_threshold_passes,
    select_candidates,
    select_eligible_assets,
    select_portfolio_size,
    summarize_benchmarks,
    summarize_k_sweep,
    summarize_portfolio,
    summarize_portfolio_rarity,
)
from helpers.schemas import read_table

alt.renderers.enable("png", embed_options={"formatLocale": LOCALE, "timeFormatLocale": LOCALE})

CHART_CONFIG = alt.Config(
    font=FONT_FAMILY,
    title=alt.TitleConfig(anchor=HELPER_PARAMETERS.title_anchor, align=HELPER_PARAMETERS.title_align),
    legend=alt.LegendConfig(orient=HELPER_PARAMETERS.legend_orient),
)

enable_inline_table_styles()

notebook_parameters = parameters().portfolios

paths = parameters().paths

prices_path = get_repo_root() / paths.prices

tables_path = get_repo_root() / paths.tables

images_path = get_repo_root() / paths.images

buy_and_hold_path = get_repo_root() / paths.buy_and_hold

portfolio_path = get_repo_root() / paths.portfolio

universe_path = get_repo_root() / paths.portfolio_universe

fee_label = pl.select(fmt_percent(pl.lit(1 - notebook_parameters.net_sale_share), decimals=2, locale=LOCALE)).item()

rank_label = {"roi": "ROI", "sharpe": "Sharpe", "sortino": "Sortino"}[notebook_parameters.rank]

tables: dict[str, GT] = {}

charts: dict[str, alt.TopLevelMixin] = {}

PORTFOLIO_LABELS = {
    "assets": "Itens",
    "days": "Dias de teste",
    "sale_fee": "Taxa de venda em % (1)",
    "roi": "ROI",
    "sharpe": "Sharpe",
    "sortino": "Sortino (2)",
}


RARITY_COLUMNS = ["candidate_assets", "selected_assets"]

SHARE_COLUMNS = ["candidate_share", "selected_share"]

PATH_LABELS = {"selected": "Selecionada", "candidates": "Todos os candidatos", "eligible": "Todos os elegíveis"}

prices = read_table("prices", prices_path).sort("name", "date")

thresholds = {
    "roi": notebook_parameters.min_roi,
    "sharpe": notebook_parameters.min_sharpe,
    "sortino": notebook_parameters.min_sortino,
}

min_roi_label = pl.select(fmt_percent(pl.lit(notebook_parameters.min_roi), decimals=0, locale=LOCALE)).item()

min_sharpe_label = pl.select(fmt_number(pl.lit(notebook_parameters.min_sharpe), decimals=3, locale=LOCALE)).item()

min_sortino_label = pl.select(fmt_number(pl.lit(notebook_parameters.min_sortino), decimals=3, locale=LOCALE)).item()

threshold_labels = {
    "candidates": f"Candidatos com preço até {notebook_parameters.max_stale_days} dias antes da validação",
    "roi": f"ROI de treinamento ≥ {min_roi_label}",
    "sharpe": f"Sharpe diário de treinamento ≥ {min_sharpe_label}",
    "sortino": f"Sortino diário de treinamento ≥ {min_sortino_label}",
    "all": "Os três limites juntos",
}

BENCHMARK_LABELS = {
    "candidates": "Todos os candidatos",
    "eligible": "Todos os elegíveis",
    "median_candidate": "Item mediano entre os candidatos",
    "random_eligible": "Itens elegíveis",
    "random_candidates": "Todos os candidatos",
}

# %% [markdown]
# ## Candidatos definidos com dados de treinamento
#
# A seleção considera apenas os dados de treinamento. Os candidatos precisam de um preço observado próximo ao
# início da validação.
#
# Os preços de entrada, saída e treinamento usam medianas das últimas observações disponíveis. Isso reduz a
# influência de um único preço sobre o ROI.
#
# Guede-Fernández et al. (2025) usam Sharpe ≥ 1, Sortino ≥ 2 e ROI ≥ 5%, mas não informam a frequência dos
# retornos. Por isso, seus limites não são diretamente comparáveis aos limites diários deste trabalho.
#
# Este trabalho adota a mesma taxa de venda de 10% do artigo, aplicada uma única vez na venda final.
# Os autores também exigem histórico diário completo. Este trabalho exige um mínimo de observações no treinamento
# e não preenche preços ausentes. A tabela informa quantos candidatos atendem a cada critério.

# %%
training_candidates = select_candidates(prices, holding_period="validation")

pass_counts = count_threshold_passes(training_candidates, thresholds)

threshold_values = pass_counts.select(fmt_integer(pl.all(), locale=LOCALE))

# %%
tables["portfolio_thresholds"] = (
    GT(build_metric_table(threshold_values, threshold_labels), locale=LOCALE)
    .tab_source_note(TABLE_SOURCE)
    .tab_source_note(
        f"Razões diárias, sem anualização. A carteira ordena os itens por {rank_label} "
        "entre os que passam nos três limites."
    )
    .cols_label(metric_name=md("**Critério**"), metric_value=md("**Itens**"))
)

# %% [markdown]
# **Candidatos que passam pelos limites de treinamento — CS:GO**

# %% jupyter={"source_hidden": true}
tables["portfolio_thresholds"]

# %% [markdown]
# ## Tamanhos de carteira na validação
#
# Os itens seguem a classificação obtida no treinamento. Os retornos da validação permitem comparar os tamanhos.
# A regra automática admite uma perda de ROI dentro da margem configurada em relação ao melhor ROI da validação.
# Entre essas carteiras, a regra escolhe o maior Sharpe diário. Em caso de empate, escolhe o menor tamanho.

# %%
sweep = summarize_k_sweep(
    prices, training_candidates, notebook_parameters.rank, thresholds, holding_period="validation"
)

selected_k = select_portfolio_size(sweep, notebook_parameters.roi_tolerance)

is_selected_size = pl.col("assets") == selected_k

selection_label = pl.when(is_selected_size).then(pl.lit("Escolhida")).otherwise(pl.lit("")).alias("selection")

sweep = sweep.with_columns(selection_label)

roi_tolerance_label = pl.select(
    fmt_number(pl.lit(notebook_parameters.roi_tolerance * 100), decimals=2, locale=LOCALE)
).item()

tables["portfolio_sweep"] = (
    GT(sweep, locale=LOCALE)
    .tab_source_note(TABLE_SOURCE)
    .tab_source_note(
        f"Itens em ordem decrescente de {rank_label} no treinamento. Retornos da validação e razões diárias. "
        "A tabela inclui apenas tamanhos com itens elegíveis suficientes. "
        f"A regra automática admite até {roi_tolerance_label} pontos percentuais "
        "abaixo do maior ROI e maximiza o Sharpe. Empates favorecem a menor carteira. "
        f"Tamanho adotado: {selected_k} itens. Somente a validação define a escolha automática."
    )
    .fmt_integer(columns=["assets"])
    .fmt_percent(columns=["roi"], decimals=2)
    .fmt_number(columns=["sharpe", "sortino"], decimals=3)
    .cols_label(
        assets=md("**Itens**"),
        roi=md("**ROI líquido**"),
        sharpe=md("**Sharpe**"),
        sortino=md("**Sortino**"),
        selection=md("**Escolha**"),
    )
)

# %% [markdown]
# **Comparação de tamanhos de carteira na validação — CS:GO**

# %% jupyter={"source_hidden": true}
tables["portfolio_sweep"]

# %% [markdown]
# A margem limita o ROI sacrificado em relação ao melhor resultado da validação.
# O teste não participa da escolha automática do tamanho da carteira.

# %% [markdown]
# ## Carteira final com treinamento e validação
#
# Após definir o tamanho, a seleção usa o histórico completo de treinamento e validação.
# O universo básico e os limites de limpeza permanecem fixos com os dados do treinamento inicial.
# As duas estratégias compartilham o universo elegível e o tamanho da carteira, mas podem escolher itens diferentes.

# %%
candidates = select_candidates(prices)

eligible = add_selection_ratios(candidates).filter(check_thresholds(thresholds)).sort("name")

selected = select_eligible_assets(candidates, selected_k, notebook_parameters.rank, thresholds)

benchmark_labels = {"selected": f"Carteira selecionada ({selected_k} itens)", **BENCHMARK_LABELS}

# %% [markdown]
# ## Raridade dos itens escolhidos e dos candidatos
#
# A tabela compara a distribuição das raridades entre os candidatos e os itens selecionados. Ela mostra se a
# seleção concentra a carteira em determinadas raridades.

# %%
rarity = summarize_portfolio_rarity(candidates, selected, prices)

tables["portfolio_rarity"] = (
    GT(rarity, locale=LOCALE)
    .tab_options(table_font_size="8pt")
    .tab_source_note(TABLE_SOURCE)
    .tab_source_note(
        "Ordem crescente de raridade, com ordem alfabética no mesmo nível. Itens sem raridade aparecem ao final."
    )
    .cols_align("left", columns="rarity")
    .fmt_integer(columns=RARITY_COLUMNS)
    .fmt_percent(columns=SHARE_COLUMNS, decimals=1)
    .cols_label(
        rarity=md("**Raridade**"),
        candidate_assets=md("**Candidatos** (1)"),
        candidate_share=md("**Parcela dos candidatos** (1)"),
        selected_assets=md("**Selecionados**"),
        selected_share=md("**Parcela dos selecionados**"),
    )
    .tab_source_note(
        f"(1) Itens com preço até {notebook_parameters.max_stale_days} dias antes do primeiro dia de teste."
    )
)

# %% [markdown]
# **Raridade dos itens da carteira — CS:GO**

# %% jupyter={"source_hidden": true}
tables["portfolio_rarity"]

# %% [markdown]
# ## Desempenho da carteira no período de teste
#
# A carteira mantém os itens selecionados, sem rebalanceamento. Nos dias sem preço observado, o cálculo mantém
# o último valor disponível para avaliar a posição.
#
# Esse procedimento não preenche a série de preços usada nas análises dos retornos dos itens. ROI, Sharpe e
# Sortino resumem o desempenho, sempre na frequência diária.
#
# A taxa de venda configurada incide uma única vez, no último dia do período.

# %%
rows = calculate_portfolio_returns(build_hold_positions(prices, selected.select("name"), selected_k))

metrics = summarize_portfolio(rows, selected_k)

portfolio_values = metrics.select(
    fmt_integer(pl.col("assets", "days"), locale=LOCALE),
    fmt_number(pl.col("sale_fee"), decimals=2, locale=LOCALE),
    fmt_percent(pl.col("roi"), decimals=2, locale=LOCALE),
    fmt_number(pl.col("sharpe", "sortino"), decimals=3, locale=LOCALE),
)

tables["portfolio"] = (
    GT(build_metric_table(portfolio_values, PORTFOLIO_LABELS), locale=LOCALE)
    .tab_source_note(TABLE_SOURCE)
    .tab_source_note(
        "Carteira igualmente ponderada nos dias de teste, sem rebalanceamento. "
        "Razões diárias com taxa livre de risco zero. Sem preço no dia, a posição mantém o último preço."
    )
    .cols_label(metric_name=md("**Métrica**"), metric_value=md("**Valor**"))
    .tab_source_note(f"(1) Taxa de venda de {fee_label} sobre a venda final.")
    .tab_source_note(
        "(2) O Sortino divide a média dos retornos diários pelo desvio-padrão amostral dos retornos negativos."
    )
)

# %% [markdown]
# **Carteira buy-and-hold — CS:GO**

# %% jupyter={"source_hidden": true}
tables["portfolio"]

# %% [markdown]
# ## Desempenho da carteira e das referências
#
# A primeira tabela compara o ROI líquido da carteira selecionada com referências fixas.
# Na segunda, a comparação com carteiras aleatórias inclui ROI, volatilidade diária e Sharpe diário.
# Os percentis da terceira tabela situam a carteira selecionada na distribuição dos sorteios.

# %%
multiples = calculate_asset_multiples(prices)

# %%
benchmark_statistics = summarize_benchmarks(prices, multiples, eligible, selected)

is_random_portfolio = pl.col("portfolio").str.starts_with("random_")

benchmarks = (
    benchmark_statistics.filter(~is_random_portfolio)
    .select("portfolio", "roi")
    .with_columns(pl.col("portfolio").replace_strict(benchmark_labels, return_dtype=pl.String))
)

tables["portfolio_benchmarks"] = (
    GT(benchmarks, locale=LOCALE)
    .tab_source_note(TABLE_SOURCE)
    .tab_source_note(f"Buy-and-hold com ponderação igual e taxa de venda de {fee_label}.")
    .cols_align("left", columns="portfolio")
    .fmt_percent(columns="roi", decimals=2)
    .cols_label(portfolio=md("**Carteira ou referência**"), roi=md("**ROI líquido**"))
)

# %% [markdown]
# **ROI líquido da carteira buy-and-hold e das referências — CS:GO**

# %% jupyter={"source_hidden": true}
tables["portfolio_benchmarks"]

# %%
random_benchmarks = benchmark_statistics.filter(is_random_portfolio)

random_comparison = pl.concat(
    [
        rows.select(
            pl.lit(f"Selecionada por {rank_label}").alias("portfolio"),
            pl.col("roi").first(),
            pl.col("return").std().alias("volatility"),
            pl.col("sharpe").first(),
        ),
        random_benchmarks.select("portfolio", "roi", "volatility", "sharpe").with_columns(
            pl.col("portfolio").replace_strict(
                {
                    "random_eligible": "Aleatórias — elegíveis (média)",
                    "random_candidates": "Aleatórias — candidatos (média)",
                },
                return_dtype=pl.String,
            )
        ),
    ]
)

random_draws_label = pl.select(fmt_integer(pl.lit(notebook_parameters.random_draws), locale=LOCALE)).item()

tables["portfolio_random"] = (
    GT(random_comparison, locale=LOCALE)
    .tab_options(table_font_size="11pt")
    .tab_source_note(TABLE_SOURCE)
    .tab_source_note(
        f"Todas as carteiras mantêm {selected_k} itens, com ponderação inicial igual e sem rebalanceamento. "
        f"Nas linhas aleatórias, cada valor representa a média em {random_draws_label} "
        "carteiras do universo indicado. Os retornos referem-se ao período de teste. "
        "Volatilidade: desvio-padrão amostral dos retornos diários. "
        "Sharpe diário, sem anualização e com taxa livre de risco zero. "
        f"As medidas incluem a taxa de venda final de {fee_label}. O Sharpe médio considera apenas valores definidos."
    )
    .cols_align("left", columns="portfolio")
    .fmt_percent(columns=["roi", "volatility"], decimals=2)
    .fmt_number(columns="sharpe", decimals=3)
    .sub_missing(columns="sharpe", missing_text="n/d")
    .cols_label(
        portfolio=md("**Carteira**"),
        roi=md("**ROI líquido**"),
        volatility=md("**Volatilidade diária**"),
        sharpe=md("**Sharpe diário**"),
    )
)

# %% [markdown]
# **Comparação direta entre carteiras buy-and-hold — CS:GO**

# %% jupyter={"source_hidden": true}
tables["portfolio_random"]

# %%
random_distribution = random_benchmarks.select(
    "portfolio", "p05", "p95", "selected_percentile", "selected_sharpe_percentile"
).with_columns(pl.col("portfolio").replace_strict(benchmark_labels, return_dtype=pl.String))

tables["portfolio_random_distribution"] = (
    GT(random_distribution, locale=LOCALE)
    .tab_options(table_font_size="9pt")
    .tab_source_note(TABLE_SOURCE)
    .tab_source_note(
        "P5 e P95 são os percentis 5 e 95 dos ROIs dos sorteios. "
        "Os percentis comparam a carteira selecionada da tabela anterior com os sorteios de cada universo. "
        "Os percentis do Sharpe consideram apenas valores definidos."
    )
    .cols_align("left", columns="portfolio")
    .fmt_percent(columns=["p05", "p95"], decimals=2)
    .fmt_percent(columns=["selected_percentile", "selected_sharpe_percentile"], decimals=0)
    .sub_missing(columns="selected_sharpe_percentile", missing_text="n/d")
    .cols_label(
        portfolio=md("**Universo dos sorteios**"),
        p05=md("**P5 do ROI**"),
        p95=md("**P95 do ROI**"),
        selected_percentile=md("**Percentil do ROI** (1)"),
        selected_sharpe_percentile=md("**Percentil do Sharpe** (1)"),
    )
    .tab_source_note(
        "(1) Parcela dos sorteios cujo ROI ou Sharpe não supera o valor correspondente da carteira selecionada."
    )
)

# %% [markdown]
# **Distribuição dos resultados das carteiras aleatórias — CS:GO**

# %% jupyter={"source_hidden": true}
tables["portfolio_random_distribution"]

# %% [markdown]
# A carteira apresenta ROI líquido positivo no teste, mas a maioria das carteiras aleatórias dos dois universos
# obtém retorno maior. A seleção pelo ROI histórico não supera a maioria dos sorteios em ROI neste período.
# O Sharpe da carteira também é inferior ao da maioria dos sorteios nos dois universos.
#
# A comparação final do modelo preditivo incluirá o buy-and-hold e carteiras aleatórias com o mesmo tamanho e
# universo elegível. O estudo manterá o período de teste, a ponderação inicial e as regras de custos comuns às
# estratégias. A tabela apresentará ROI, volatilidade diária, Sharpe diário e os percentis das estratégias entre
# os sorteios.

# %% [markdown]
# ## Evolução das carteiras no teste
#
# As curvas mostram a evolução do valor das carteiras durante o teste, antes da taxa de venda. A escala
# usa o capital inicial como referência. A comparação permite observar o desempenho ao longo do período,
# não apenas no encerramento.

# %%
groups = {"selected": selected, "candidates": candidates, "eligible": eligible}

path_labels = {
    label: f"{PATH_LABELS[label]} ({pl.select(fmt_integer(pl.lit(assets.height), locale=LOCALE)).item()} itens)"
    for label, assets in groups.items()
}

paths = build_benchmark_paths(prices, groups).with_columns(
    pl.col("portfolio").replace_strict(path_labels, return_dtype=pl.String)
)

charts["portfolio_value"] = (
    alt.Chart(paths)
    .mark_line(color="black")
    .encode(
        x=alt.X("date:T", title="Dia"),
        y=alt.Y("value:Q", title="Índice de valor da carteira (base 1)", scale=alt.Scale(zero=False)),
        strokeDash=alt.StrokeDash("portfolio:N", title="Carteira"),
    )
    .properties(
        width=HELPER_PARAMETERS.chart_width,
        height=HELPER_PARAMETERS.chart_height,
        title=alt.Title(
            wrap_chart_note(
                "Capital inicial = 1. Ponderação inicial igual, sem rebalanceamento.",
                f"Valores antes da taxa de venda final de {fee_label}.",
            ),
            anchor="start",
            orient="bottom",
            fontSize=10,
            fontWeight="normal",
        ),
    )
    .properties(config=CHART_CONFIG)
)

# %% [markdown]
# **Valor das carteiras nos dias de teste**

# %% jupyter={"source_hidden": true}
charts["portfolio_value"]

# %% [markdown]
# ## Contribuição de cada item
#
# A tabela mostra a razão entre os preços de saída e entrada de cada item. Também informa quanto cada posição
# contribui para o retorno bruto da carteira.
#
# Essa decomposição permite verificar se poucos itens concentram o resultado.

# %%
contributions = calculate_item_contributions(selected, multiples, prices)

tables["portfolio_items"] = (
    GT(contributions, locale=LOCALE)
    .tab_options(table_font_size="6pt")
    .tab_source_note(TABLE_SOURCE)
    .tab_source_note(
        "ROI hist.: ROI de seleção no histórico. Entrada e saída em US$, como mediana das últimas observações."
    )
    .cols_align("left", columns=["name", "rarity"])
    .fmt_percent(columns=["roi", "contribution"], decimals=1)
    .fmt_number(columns=["entry_price", "exit_price", "multiple"], decimals=2)
    .cols_label(
        name=md("**Item**"),
        rarity=md("**Raridade**"),
        roi=md("**ROI hist.**"),
        entry_price=md("**Entrada**"),
        exit_price=md("**Saída**"),
        multiple=md("**Múltiplo** (1)"),
        contribution=md("**Contrib.** (2)"),
    )
    .tab_source_note("(1) Razão entre os preços de saída e entrada.")
    .tab_source_note("(2) (Múltiplo - 1) dividido pelo número de itens, antes da taxa de venda.")
)

# %% [markdown]
# **Contribuição de cada item da carteira — CS:GO**

# %% jupyter={"source_hidden": true}
tables["portfolio_items"]

# %% jupyter={"source_hidden": true, "outputs_hidden": true}
for path in (buy_and_hold_path, portfolio_path, universe_path):
    path.parent.mkdir(parents=True, exist_ok=True)
    print(f"Written {path}")

rows.write_parquet(buy_and_hold_path)

metrics.write_parquet(portfolio_path)

eligible.select("name").sort("name").write_parquet(universe_path)

write_outputs(tables, charts, tables_path, images_path)
