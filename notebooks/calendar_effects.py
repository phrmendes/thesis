# %% [markdown]
# # Retornos nas promoções e nos dias da semana — CS:GO
#
# Glaus (2022) identifica diferenças nos retornos em torno das promoções sazonais da Steam. Este notebook
# examina esse padrão nas fases da promoção, nas raridades e nos dias da semana.
#
# A amostra contém dez promoções. As estimativas descrevem relações entre calendário e retornos, sem
# identificar efeitos causais.

# %% jupyter={"source_hidden": true}
import polars as pl
from great_tables import GT, md
from great_tables.vals import fmt_number
from helpers.diagnostics import tabulate_joint_tests
from helpers.export import enable_inline_table_styles, write_outputs
from helpers.formatting import LOCALE, TABLE_SOURCE
from helpers.market import get_market_series
from helpers.parameters import parameters
from helpers.paths import get_repo_root
from helpers.sales import (
    add_sale_calendar,
    estimate_segment_phase_effects,
    estimate_weekday_effects,
    fit_phase_model,
    fit_sale_regression,
    fit_segment_models,
    run_weekday_test,
    summarize_phase_lag_sensitivity,
    summarize_sale_phases,
    summarize_weekday_lag_sensitivity,
)
from helpers.schemas import read_table
from helpers.segments import build_rarity_segment

enable_inline_table_styles()

notebook_parameters = parameters().calendar_effects

paths = parameters().paths

prices_path = get_repo_root() / paths.prices

tables_path = get_repo_root() / paths.tables

tables: dict[str, GT] = {}

MIN_SEGMENT_ITEMS = notebook_parameters.min_segment_items

EQUAL_LABEL = "Ponderação igual"

WEIGHTED_LABEL = "Ponderado por preço"

PHASE_LABELS = {
    "const": "Dias fora de promoção (1)",
    "pre": "Pré-promoção (2)",
    "fh": "Promoção, primeira metade",
    "sh": "Promoção, segunda metade",
    "post": "Pós-promoção (3)",
    "turn_of_year": "Virada do ano",
}

ITEM_PHASE_LABELS = {
    "none": "Dias fora de promoção",
    "pre": "Pré-promoção (1)",
    "fh": PHASE_LABELS["fh"],
    "sh": PHASE_LABELS["sh"],
    "post": "Pós-promoção (2)",
}

WEEKDAY_LABELS = {
    1: "Segunda",
    2: "Terça",
    3: "Quarta",
    4: "Quinta",
    5: "Sexta",
    6: "Sábado",
    7: "Domingo",
}


def build_plain_test_table(frame: pl.DataFrame, model_label: str) -> GT:
    """Build the table of a test that has one statistic and one p-value for each model.

    Returns:
        The formatted table.

    """
    return (
        GT(frame, locale=LOCALE)
        .tab_source_note(TABLE_SOURCE)
        .cols_align("left", columns="model")
        .fmt_number(columns=["statistic"], decimals=2)
        .fmt_number(columns=["p_value"], decimals=3)
        .cols_label(model=md(f"**{model_label}**"), statistic=md("**Estatística**"), p_value=md("**p**"))
    )


prices = read_table("prices", prices_path)

# %% [markdown]
# ## Retornos e índice de mercado
#
# ### Retorno médio
#
# $$
# R_t = \frac{1}{n_t} \sum_{i=1}^{n_t} r_{i,t}.
# $$
#
# $t$ representa o dia, e $i$ representa o item. O retorno do item $i$ no dia $t$ é $r_{i,t}$.
# O número de itens com retorno observado nesse dia é $n_t$.
#
# ### Retorno ponderado pelo preço
#
# O retorno ponderado usa como ponderador o preço do item no dia observado anterior, $t^-$, ou seja, $p_{i,t^-}$:
#
# $$
# R_t^{\mathrm{pond}} = \frac{\sum_{i=1}^{n_t} p_{i,t^-} r_{i,t}}{\sum_{i=1}^{n_t} p_{i,t^-}}.
# $$
#
# ### Índice de mercado
#
# O índice acumula a média geométrica diária, $G_t$, dos retornos brutos, $1 + r_{i,t}$. Essa escolha reduz o
# efeito do ruído dos preços. O código usa a segunda forma, que evita o produto de milhares de números:
#
# $$
# G_t = \left(\prod_{i=1}^{n_t} (1 + r_{i,t})\right)^{1/n_t}
# = \exp\!\left(\frac{1}{n_t} \sum_{i=1}^{n_t} \ln(1 + r_{i,t})\right),
# \qquad 1 + r_{i,t} > 0.
# $$
#
# A igualdade exige retornos brutos positivos. Isso vale aqui, porque os preços são positivos.
#
# O índice começa em 1 e muda a cada dia pela média geométrica do dia:
#
# $$
# I_0 = 1, \qquad I_t = I_{t-1} G_t.
# $$

# %%
market = get_market_series(prices)

market

# %% [markdown]
# ## Retornos por fase da promoção
#
# A tabela resume os retornos diários dos itens em cada fase da promoção. A definição das fases é a mesma da
# regressão seguinte.
#
# O período de referência exclui a pré-promoção, a promoção e a pós-promoção. As observações de um mesmo dia e
# de um mesmo item não são independentes.

# %%
item_phases = summarize_sale_phases(prices).with_columns(
    pl.col("phase")
    .cast(pl.String)
    .replace_strict(
        ITEM_PHASE_LABELS,
        return_dtype=pl.String,
    )
)

tables["item_phases"] = (
    GT(item_phases, locale=LOCALE)
    .tab_options(table_font_size="9.5pt")
    .tab_source_note(TABLE_SOURCE)
    .tab_source_note(
        "DP: desvio padrão. "
        "N. de observações conta os retornos válidos dos itens em cada data. "
        "O mesmo item pode aparecer em várias datas."
    )
    .cols_align("left", columns="phase")
    .fmt_integer(columns=["item_days"])
    .fmt_percent(columns=["mean_return", "median_return", "std_return"], decimals=2)
    .fmt_percent(columns=["positive_share"], decimals=1)
    .cols_label(
        phase=md("**Fase**"),
        item_days=md("**N. de observações**"),
        mean_return=md("**Média**"),
        median_return=md("**Mediana**"),
        std_return=md("**DP**"),
        positive_share=md("**Retornos positivos**"),
    )
    .tab_source_note("(1) A pré-promoção dura metade da promoção.")
    .tab_source_note("(2) A pós-promoção dura a promoção inteira.")
)

# %% [markdown]
# **Retornos diários dos itens por fase da promoção — CS:GO**

# %% jupyter={"source_hidden": true}
tables["item_phases"]

# %% [markdown]
# ## Diferenças de retorno por fase da promoção
#
# O modelo segue Glaus (2022) e usa o retorno diário do mercado como variável dependente. A pré-promoção
# abrange metade da duração da promoção, e a pós-promoção abrange a duração inteira. O período da promoção se divide
# em duas metades. A primeira inclui o dia excedente quando a duração é ímpar. O modelo controla a virada
# do ano, que coincide parcialmente com as promoções de inverno.
#
# A notação segue Wooldridge (equação 12.40):
#
# $$
# y_t = \beta_0 + \beta_1 x_{t1} + \cdots + \beta_5 x_{t5} + u_t.
# $$
#
# $y_t$ é o retorno diário do mercado, com ponderação igual ou por preço. As variáveis $x_{t1}, \ldots, x_{t5}$
# indicam, nessa ordem, a pré-promoção, a primeira metade, a segunda metade, a pós-promoção e a virada do ano.
# Cada variável vale 1 no período correspondente e 0 nos demais dias. $\beta_0$ é a constante, $\beta_j$ é o
# coeficiente da variável $j$ e $u_t$ é o erro não observado.
#
# A análise estima as regressões por mínimos quadrados ordinários, com erros-padrão HAC de Newey-West.
# Essa correção permite inferência robusta à heterocedasticidade e à correlação serial,
# sob as condições de validade do método.
# A análise usa HAC diretamente, sem testes preliminares para escolher a correção.

# %%
phases = fit_sale_regression(market).with_columns(pl.col("term").replace_strict(PHASE_LABELS, return_dtype=pl.String))

tables["sale_phases"] = (
    GT(phases, locale=LOCALE)
    .tab_source_note(TABLE_SOURCE)
    .tab_source_note(
        "Regressão do retorno diário de mercado nas variáveis de fase e de virada do ano. "
        "Erros-padrão de Newey-West, com defasagens pela regra apresentada por Wooldridge."
    )
    .tab_options(table_font_size="11pt")
    .cols_align("left", columns="term")
    .fmt_integer(columns=["days"])
    .fmt_percent(
        columns=["equal_coefficient", "weighted_coefficient"],
        decimals=2,
    )
    .fmt_number(columns=["equal_statistic", "weighted_statistic"], decimals=2)
    .fmt_number(columns=["equal_p_value", "weighted_p_value"], decimals=3)
    .tab_spanner(label=md("**Ponderação igual**"), columns=["equal_coefficient", "equal_statistic", "equal_p_value"])
    .tab_spanner(
        label=md("**Ponderado por preço** (4)"),
        columns=["weighted_coefficient", "weighted_statistic", "weighted_p_value"],
    )
    .cols_label(
        term=md("**Fase**"),
        days=md("**Dias**"),
        equal_coefficient=md("**Coef.**"),
        equal_statistic=md("**t**"),
        equal_p_value=md("**p**"),
        weighted_coefficient=md("**Coef.**"),
        weighted_statistic=md("**t**"),
        weighted_p_value=md("**p**"),
    )
    .tab_source_note("(1) A constante é a média dos dias fora de promoção.")
    .tab_source_note("(2) Período anterior à promoção, com metade de sua duração.")
    .tab_source_note("(3) Período posterior à promoção, com duração igual à da promoção.")
    .tab_source_note("(4) A ponderação usa o preço da observação anterior.")
)

# %% [markdown]
# **Retorno diário do mercado por fase da promoção — CS:GO**

# %% jupyter={"source_hidden": true}
tables["sale_phases"]

# %% [markdown]
# ### Diferença das fases em relação ao período de referência
#
# Os testes individuais avaliam um coeficiente por vez. O teste de Wald avalia os quatro coeficientes de fase
# em conjunto:
#
# $$
# H_0: \beta_1 = \beta_2 = \beta_3 = \beta_4 = 0.
# $$
#
# O teste de Wald avalia os quatro coeficientes em conjunto, com covariância de Newey-West.
# A constante $\beta_0$ e o coeficiente da virada do ano $\beta_5$ ficam fora do teste.
# Sob a hipótese nula, a estatística segue aproximadamente uma $\chi^2$ com quatro graus de liberdade.

# %%
phase_data = add_sale_calendar(market)

phase_models = {
    EQUAL_LABEL: fit_phase_model(phase_data, "return"),
    WEIGHTED_LABEL: fit_phase_model(phase_data, "weighted_return"),
}

tables["phases_joint"] = build_plain_test_table(
    tabulate_joint_tests(phase_models),
    "Retorno do mercado",
)

# %% [markdown]
# **Teste conjunto das fases da promoção**

# %% jupyter={"source_hidden": true}
tables["phases_joint"]

# %% [markdown]
# O teste rejeita a hipótese de que os quatro coeficientes de fase são zero nas duas ponderações.
# Os p-valores são 0,003 com ponderação igual e 0,006 com ponderação por preço. Pelo menos uma fase apresenta
# retorno médio diferente do período de referência, após controlar a virada do ano.

# %% [markdown]
# ### Sensibilidade das conclusões sobre as fases às defasagens
#
# O número de defasagens de Newey-West muda os erros padrão. A análise aplica a regra de
# Newey-West apresentada por Wooldridge (§12.5): $\lfloor 4 (n/100)^{2/9} \rfloor$, onde $n$ conta as observações
# da regressão após excluir valores ausentes. Com 983 observações, a regra dá 6 defasagens.
# Uma lacuna pode separar duas observações consecutivas. A tabela compara 5, 6, 7 e 14 defasagens e mostra o
# p-valor de duas fases. Ela verifica se a escolha das defasagens altera a conclusão.

# %%
phase_lags = summarize_phase_lag_sensitivity(phase_data, {"equal": "return", "weighted": "weighted_return"})

tables["phases_lags"] = (
    GT(phase_lags, locale=LOCALE)
    .tab_source_note(TABLE_SOURCE)
    .tab_source_note("P-valores dos coeficientes. Os coeficientes são os mesmos em todas as linhas.")
    .fmt_integer(columns=["lags"])
    .fmt_number(
        columns=[column for column in phase_lags.columns if column.endswith("p_value")],
        decimals=3,
    )
    .tab_spanner(label=md(f"**{EQUAL_LABEL}**"), columns=["equal_fh_p_value", "equal_post_p_value"])
    .tab_spanner(label=md(f"**{WEIGHTED_LABEL}**"), columns=["weighted_fh_p_value", "weighted_post_p_value"])
    .cols_label(
        lags=md("**Defasagens**"),
        equal_fh_p_value=md("**1ª metade**"),
        equal_post_p_value=md("**Pós-promoção**"),
        weighted_fh_p_value=md("**1ª metade**"),
        weighted_post_p_value=md("**Pós-promoção**"),
    )
)

# %% [markdown]
# **Sensibilidade às defasagens de Newey-West — fases da promoção**

# %% jupyter={"source_hidden": true}
tables["phases_lags"]

# %% [markdown]
# A primeira metade permanece significativa a 5% nas duas ponderações, em todas as defasagens testadas.
# A pós-promoção permanece significativa apenas com ponderação igual. Nesse caso, o p-valor chega a 0,049
# com 14 defasagens, próximo do limite de 5%.

# %% [markdown]
# ## Retornos por fase dentro de cada raridade
#
# A análise estima uma regressão para cada raridade que atinge o mínimo de itens definido nos parâmetros.
# A tabela apresenta os coeficientes da primeira metade e da pós-promoção.
#
# Em cada regressão, $y_t$ representa o retorno médio diário dos itens daquela raridade. Os demais termos
# seguem a mesma definição da regressão de mercado.

# %%
by_rarity = estimate_segment_phase_effects(prices, build_rarity_segment(), MIN_SEGMENT_ITEMS)

tables["sale_rarity"] = (
    GT(by_rarity, locale=LOCALE)
    .tab_source_note(TABLE_SOURCE)
    .tab_source_note(
        f"Raridades com pelo menos {MIN_SEGMENT_ITEMS} itens, em ordem decrescente do número de itens. "
        "Retorno com ponderação igual dentro de cada raridade e erros-padrão de Newey-West."
    )
    .cols_align("left", columns="segment")
    .fmt_integer(columns=["items"])
    .fmt_percent(columns=["fh_coefficient", "post_coefficient"], decimals=2)
    .fmt_number(columns=["fh_statistic", "post_statistic"], decimals=2)
    .fmt_number(columns=["fh_p_value", "post_p_value"], decimals=3)
    .tab_spanner(label=md("**Promoção, primeira metade**"), columns=["fh_coefficient", "fh_statistic", "fh_p_value"])
    .tab_spanner(label=md("**Pós-promoção**"), columns=["post_coefficient", "post_statistic", "post_p_value"])
    .cols_label(
        segment=md("**Raridade**"),
        items=md("**Itens**"),
        fh_coefficient=md("**Coef.**"),
        fh_statistic=md("**t**"),
        fh_p_value=md("**p**"),
        post_coefficient=md("**Coef.**"),
        post_statistic=md("**t**"),
        post_p_value=md("**p**"),
    )
)

# %% [markdown]
# **Efeito da promoção por raridade — CS:GO**

# %% jupyter={"source_hidden": true}
tables["sale_rarity"]

# %% [markdown]
# A primeira metade apresenta coeficientes negativos em todas as raridades. Na pós-promoção, os coeficientes
# são positivos, exceto em Consumer Grade, cuja estimativa fica próxima de zero. As regressões separadas não
# testam se os coeficientes diferem entre raridades.

# %% [markdown]
# ### Teste conjunto das fases dentro de cada raridade
#
# A análise estima uma regressão para cada raridade. O teste de Wald avalia os quatro coeficientes de fase
# em conjunto, com covariância HAC. O teste verifica se pelo menos uma fase tem retorno médio diferente dos
# dias fora de promoção. A regressão inclui o controle da virada do ano. Cada linha representa uma raridade,
# sem comparação entre raridades.

# %%
rarity_models = fit_segment_models(prices, build_rarity_segment(), MIN_SEGMENT_ITEMS)

tables["rarity_joint"] = build_plain_test_table(
    tabulate_joint_tests(rarity_models),
    "Raridade",
)

# %% [markdown]
# **Teste de Wald das fases em cada raridade**

# %% jupyter={"source_hidden": true}
tables["rarity_joint"]

# %% [markdown]
# O teste detecta diferenças a 5% em seis raridades: Restricted, Classified, Mil-Spec Grade, High Grade,
# Exotic e Base Grade. Nesses casos, pelo menos uma fase tem retorno médio diferente do período de referência.
# Nas outras cinco raridades, a evidência não basta para detectar essa diferença.
# Em High Grade, o p-valor de 0,048 fica próximo do limite de 5%.

# %% [markdown]
# ## Retornos médios por dia da semana
#
# A regressão estima o retorno médio do mercado em cada dia da semana, sem constante. O objetivo é
# verificar se os retornos médios diferem entre os dias:
#
# $$
# y_t = \beta_1 x_{t1} + \cdots + \beta_7 x_{t7} + u_t.
# $$
#
# Neste modelo, $y_t$ é o retorno diário do mercado. As variáveis $x_{t1}, \ldots, x_{t7}$ indicam os dias de
# segunda a domingo. Cada variável vale 1 no dia correspondente e 0 nos demais dias. O coeficiente $\beta_j$
# é a média do retorno no dia $j$ e $u_t$ é o erro. O teste conjunto verifica se as sete médias são iguais:
#
# $$
# H_0: \beta_1 = \beta_2 = \cdots = \beta_7.
# $$

# %%
joint = run_weekday_test(market).row(0, named=True)

weekdays = estimate_weekday_effects(market).with_columns(
    pl.col("weekday").replace_strict(
        WEEKDAY_LABELS,
        return_dtype=pl.String,
    )
)

equal_p_value_label = pl.select(fmt_number(pl.lit(joint["equal_p_value"]), decimals=3, locale=LOCALE)).item()

weighted_p_value_label = pl.select(fmt_number(pl.lit(joint["weighted_p_value"]), decimals=3, locale=LOCALE)).item()

tables["weekday"] = (
    GT(weekdays, locale=LOCALE)
    .tab_source_note(TABLE_SOURCE)
    .tab_source_note(
        "Média do retorno de mercado em cada dia da semana, com erros-padrão de Newey-West. "
        "As defasagens seguem a regra apresentada por Wooldridge. "
        f"Teste conjunto de médias iguais: p = {equal_p_value_label} (ponderação igual) e "
        f"p = {weighted_p_value_label} (ponderado por preço)."
    )
    .cols_align("left", columns="weekday")
    .fmt_percent(columns=["equal_coefficient", "weighted_coefficient"], decimals=2)
    .fmt_number(columns=["equal_statistic", "weighted_statistic"], decimals=2)
    .fmt_number(columns=["equal_p_value", "weighted_p_value"], decimals=3)
    .tab_spanner(label=md("**Ponderação igual**"), columns=["equal_coefficient", "equal_statistic", "equal_p_value"])
    .tab_spanner(
        label=md("**Ponderado por preço**"), columns=["weighted_coefficient", "weighted_statistic", "weighted_p_value"]
    )
    .cols_label(
        weekday=md("**Dia**"),
        equal_coefficient=md("**Média**"),
        equal_statistic=md("**t**"),
        equal_p_value=md("**p** (1)"),
        weighted_coefficient=md("**Média**"),
        weighted_statistic=md("**t**"),
        weighted_p_value=md("**p** (1)"),
    )
    .tab_source_note("(1) O p-valor testa se a média do dia é zero.")
)

# %% [markdown]
# **Retorno diário do mercado por dia da semana — CS:GO**

# %% jupyter={"source_hidden": true}
tables["weekday"]

# %% [markdown]
# Com ponderação igual, o teste conjunto rejeita médias iguais entre os dias da semana (p = 0,026).
# Com ponderação por preço, não rejeita (p = 0,147). A evidência de diferenças entre dias depende da ponderação.

# %% [markdown]
# ### Sensibilidade da conclusão sobre os dias da semana às defasagens
#
# O teste conjunto das sete médias depende do número de defasagens de Newey-West. A tabela refaz o teste
# com 5, 6, 7 e 14 defasagens.

# %%
weekday_lags = summarize_weekday_lag_sensitivity(market)

tables["weekday_lags"] = (
    GT(weekday_lags, locale=LOCALE)
    .tab_source_note(TABLE_SOURCE)
    .tab_source_note("P-valor do teste conjunto de médias iguais.")
    .fmt_integer(columns=["lags"])
    .fmt_number(columns=["equal_p_value", "weighted_p_value"], decimals=3)
    .cols_label(
        lags=md("**Defasagens**"), equal_p_value=md(f"**{EQUAL_LABEL}**"), weighted_p_value=md(f"**{WEIGHTED_LABEL}**")
    )
)

# %% [markdown]
# **Sensibilidade às defasagens de Newey-West — dia da semana**

# %% jupyter={"source_hidden": true}
tables["weekday_lags"]

# %% [markdown]
# A conclusão se mantém em todas as defasagens testadas: o teste rejeita médias iguais apenas com ponderação igual.
# Os p-valores variam de 0,022 a 0,040 nessa ponderação e de 0,147 a 0,176 na ponderação por preço.

# %% jupyter={"source_hidden": true, "outputs_hidden": true}
write_outputs(tables, {}, tables_path)
