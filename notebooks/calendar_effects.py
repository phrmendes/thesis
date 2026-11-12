# %% [markdown]
# # Efeitos de calendário nos retornos dos itens CS:GO
#
# Glaus (2022) mostra que os retornos de itens da Steam mudam em torno das promoções sazonais da loja. Este
# caderno testa esse efeito nos dados. A ordem vai do geral ao específico: as temporadas de promoção, a
# regressão por fase, o retorno em cada promoção, a atividade de negociação, a divisão por raridade e o
# efeito do dia da semana. Todas as estimativas descrevem associações. Com dez promoções, nenhuma isola uma
# causa.

# %%
from argparse import ArgumentParser
from pathlib import Path

import polars as pl
from great_tables import GT
from helpers.export import inline_table_styles, write_outputs
from helpers.formatting import DEC_MARK, SEP_MARK, format_metric
from helpers.market import market_series
from helpers.paths import repo
from helpers.runtime import notebook_arguments
from helpers.sales import (
    activity_regression,
    sale_event_summary,
    sale_regression,
    sale_season_summary,
    segment_phase_effects,
    weekday_effects,
    weekday_joint_test,
)
from helpers.schemas import read_table
from helpers.segments import rarity_segment

# %%
# GitHub drops style blocks, so the tables keep their styles inline.
inline_table_styles()

WIDE_TABLES = frozenset({"sale_phases", "sale_rarity"})

MIN_SEGMENT_ITEMS = 100

SEASON_LABELS = {
    "none": "Fora de promoção",
    "autumn": "Promoção de outono",
    "winter": "Promoção de inverno",
    "summer": "Promoção de verão",
    "spring": "Promoção de primavera",
}

PHASE_LABELS = {
    "const": "Dias fora de promoção",
    "pre": "Pré-venda",
    "fh": "Promoção, primeira metade",
    "sh": "Promoção, segunda metade",
    "post": "Pós-venda",
    "turn_of_year": "Virada do ano",
}

WEEKDAY_LABELS = {1: "Segunda", 2: "Terça", 3: "Quarta", 4: "Quinta", 5: "Sexta", 6: "Sábado", 7: "Domingo"}

# %% [markdown]
# ## Argumentos da linha de comando

# %%
parser = ArgumentParser(description="Calendário: promoções da Steam e dia da semana.")
parser.add_argument("--prices", type=Path, default=repo() / "files/prices.parquet", help="Preços diários limpos.")
parser.add_argument("--tables", type=Path, default=repo() / "output/tables", help="Pasta para os arquivos das tabelas.")
args = parser.parse_args(notebook_arguments())

# %%
prices = read_table("prices", args.prices)
market = market_series(prices)

# %% [markdown]
# ## Comparar os retornos por temporada de promoção
#
# Glaus (2022) encontra retornos menores no início e maiores depois das promoções sazonais da Steam. Esta
# tabela compara os retornos diários dos itens por temporada de promoção. A comparação é descritiva: as
# observações item-dia são dependentes, então a tabela não testa um efeito causal.

# %%
seasons = sale_season_summary(prices)
seasons_text = seasons.with_columns(pl.col("sale_season").replace_strict(SEASON_LABELS, return_dtype=pl.String))

seasons_gt = (
    GT(seasons_text)
    .cols_align("left", columns="sale_season")
    .tab_header(title="Retornos Diários por Temporada de Promoção — CS:GO")
    .fmt_integer(columns=["item_days"], sep_mark=SEP_MARK)
    .fmt_percent(
        columns=["mean_return", "median_return", "std_return"], decimals=2, sep_mark=SEP_MARK, dec_mark=DEC_MARK
    )
    .fmt_percent(columns=["positive_share"], decimals=1, sep_mark=SEP_MARK, dec_mark=DEC_MARK)
    .cols_label(
        sale_season="Temporada",
        item_days="Itens-dia",
        mean_return="Média",
        median_return="Mediana",
        std_return="DP",
        positive_share="Dias positivos",
    )
    .tab_source_note(
        "DP: desvio padrão. Um dia pertence a uma temporada quando cai dentro do período da promoção da Steam. "
        "Comparação descritiva: as observações item-dia são dependentes, então a tabela não testa "
        "um efeito causal de promoção."
    )
)
seasons_gt

# %% [markdown]
# ## Estimar o efeito de cada fase da promoção
#
# A regressão segue Glaus (2022): retorno diário do mercado, como o retorno de portfólio dele, e erros de
# Newey-West. A pré-venda tem metade da duração da promoção, a pós-venda tem a duração inteira, e a
# promoção se divide em primeira e segunda metade. A virada do ano entra como controle, porque a promoção
# de inverno cobre o fim do ano.

# %%
phases = sale_regression(market)
phases_text = phases.with_columns(pl.col("term").replace_strict(PHASE_LABELS, return_dtype=pl.String))

phases_gt = (
    GT(phases_text)
    .cols_align("left", columns="term")
    .tab_header(title="Retorno Diário do Mercado por Fase da Promoção — CS:GO")
    .fmt_integer(columns=["days"], sep_mark=SEP_MARK)
    .fmt_percent(
        columns=["equal_coefficient", "weighted_coefficient"], decimals=2, sep_mark=SEP_MARK, dec_mark=DEC_MARK
    )
    .fmt_number(columns=["equal_statistic", "weighted_statistic"], decimals=2, sep_mark=SEP_MARK, dec_mark=DEC_MARK)
    .fmt_number(columns=["equal_p_value", "weighted_p_value"], decimals=3, sep_mark=SEP_MARK, dec_mark=DEC_MARK)
    .tab_spanner(label="Peso igual", columns=["equal_coefficient", "equal_statistic", "equal_p_value"])
    .tab_spanner(label="Peso por preço", columns=["weighted_coefficient", "weighted_statistic", "weighted_p_value"])
    .cols_label(
        term="Fase",
        days="Dias",
        equal_coefficient="Coef.",
        equal_statistic="t",
        equal_p_value="p",
        weighted_coefficient="Coef.",
        weighted_statistic="t",
        weighted_p_value="p",
    )
    .tab_source_note(
        "Regressão do retorno diário do mercado sobre variáveis binárias de fase e da virada do ano, com erros de "
        "Newey-West (7 defasagens). A constante é a média dos dias fora de promoção. "
        "Pré-venda: metade da duração da promoção antes. Pós-venda: a duração da promoção depois. "
        "O peso por preço usa o preço do dia anterior com preço. Estimativas descritivas: a virada do ano está "
        "dentro da promoção de inverno e a amostra tem dez promoções."
    )
)
phases_gt

# %% [markdown]
# ## Conferir cada promoção
#
# Glaus (2022) testa se uma única promoção explica o resultado. A tabela por evento mostra o retorno
# diário médio do mercado em cada fase de cada promoção.

# %%
events = sale_event_summary(market)
events_text = events.with_columns(
    pl.col("event_year").cast(pl.String),
    pl.col("event_season").replace_strict(SEASON_LABELS, return_dtype=pl.String),
    pl.col("first_sale_day").dt.strftime("%d/%m/%Y"),
)

events_gt = (
    GT(events_text)
    .cols_align("left", columns=["event_year", "event_season"])
    .tab_header(title="Retorno Diário do Mercado em Torno de Cada Promoção — CS:GO")
    .fmt_percent(
        columns=["pre_return", "fh_return", "sh_return", "post_return"],
        decimals=2,
        sep_mark=SEP_MARK,
        dec_mark=DEC_MARK,
    )
    .sub_missing(missing_text="n/d")
    .cols_label(
        event_year="Ano",
        event_season="Promoção",
        first_sale_day="Primeiro dia",
        sale_days="Dias",
        pre_return="Pré-venda",
        fh_return="1ª metade",
        sh_return="2ª metade",
        post_return="Pós-venda",
    )
    .tab_source_note(
        "Média do retorno diário do mercado (peso igual) em cada fase. "
        "n/d: o dia pertence à fase de outra promoção ou fica fora da amostra."
    )
)
events_gt

# %% [markdown]
# ## Medir a atividade de negociação nas promoções
#
# Glaus (2022) liga o efeito de promoção a um volume maior nos dias de promoção. A fonte não traz volume.
# O substituto é a parcela dos itens listados que tem preço de 24 horas no dia, ou seja, que teve ao menos
# uma venda. A regressão usa as mesmas fases. A parcela mede se o item negocia, não quanto. A qualidade da
# captura do dia também a move, então o resultado é só um indício.

# %%
activity = activity_regression(prices)
activity_text = activity.with_columns(pl.col("term").replace_strict(PHASE_LABELS, return_dtype=pl.String))

activity_gt = (
    GT(activity_text)
    .cols_align("left", columns="term")
    .tab_header(title="Atividade de Negociação por Fase da Promoção — CS:GO")
    .fmt_integer(columns=["days"], sep_mark=SEP_MARK)
    .fmt_percent(columns=["activity_coefficient"], decimals=2, sep_mark=SEP_MARK, dec_mark=DEC_MARK)
    .fmt_number(columns=["activity_statistic"], decimals=2, sep_mark=SEP_MARK, dec_mark=DEC_MARK)
    .fmt_number(columns=["activity_p_value"], decimals=3, sep_mark=SEP_MARK, dec_mark=DEC_MARK)
    .cols_label(
        term="Fase",
        days="Dias",
        activity_coefficient="Coef. (pontos percentuais)",
        activity_statistic="t",
        activity_p_value="p",
    )
    .tab_source_note(
        "Variável: itens com preço de 24 horas no dia sobre itens listados até o dia. Newey-West (7 defasagens). "
        "A constante é a parcela média dos dias fora de promoção. Substituto do volume de Glaus (2022)."
    )
)
activity_gt

# %% [markdown]
# ## Separar o efeito por raridade
#
# Glaus (2022) testa se o efeito vem de itens com características específicas. A tabela repete a regressão
# do mercado dentro de cada raridade com ao menos 100 itens e mostra a primeira metade da promoção e o
# pós-venda.

# %%
by_rarity = segment_phase_effects(prices, rarity_segment(), MIN_SEGMENT_ITEMS)

rarity_gt = (
    GT(by_rarity)
    .cols_align("left", columns="segment")
    .tab_header(title="Efeito da Promoção por Raridade — CS:GO")
    .fmt_integer(columns=["items"], sep_mark=SEP_MARK)
    .fmt_percent(columns=["fh_coefficient", "post_coefficient"], decimals=2, sep_mark=SEP_MARK, dec_mark=DEC_MARK)
    .fmt_number(columns=["fh_statistic", "post_statistic"], decimals=2, sep_mark=SEP_MARK, dec_mark=DEC_MARK)
    .tab_spanner(label="Promoção, primeira metade", columns=["fh_coefficient", "fh_statistic"])
    .tab_spanner(label="Pós-venda", columns=["post_coefficient", "post_statistic"])
    .cols_label(
        segment="Raridade",
        items="Itens",
        fh_coefficient="Coef.",
        fh_statistic="t",
        post_coefficient="Coef.",
        post_statistic="t",
    )
    .tab_source_note(
        f"Raridades com {MIN_SEGMENT_ITEMS} itens ou mais, em ordem de tamanho. Mercado de peso igual dentro da "
        "raridade, com a mesma regressão da tabela de fases e erros de Newey-West."
    )
)
rarity_gt

# %% [markdown]
# ## Verificar o efeito do dia da semana
#
# O dia da semana é outra anomalia de calendário de dados diários. A regressão estima o retorno médio do
# mercado em cada dia da semana, sem constante, e o teste conjunto verifica se as sete médias são iguais.
# Se o padrão semanal for fraco, as fases de promoção não refletem o dia da semana em que caem.

# %%
weekdays = weekday_effects(market)
joint = weekday_joint_test(market).row(0, named=True)
weekdays_text = weekdays.with_columns(pl.col("weekday").replace_strict(WEEKDAY_LABELS, return_dtype=pl.String))

weekday_gt = (
    GT(weekdays_text)
    .cols_align("left", columns="weekday")
    .tab_header(title="Retorno Diário do Mercado por Dia da Semana — CS:GO")
    .fmt_percent(
        columns=["equal_coefficient", "weighted_coefficient"], decimals=2, sep_mark=SEP_MARK, dec_mark=DEC_MARK
    )
    .fmt_number(columns=["equal_statistic", "weighted_statistic"], decimals=2, sep_mark=SEP_MARK, dec_mark=DEC_MARK)
    .tab_spanner(label="Peso igual", columns=["equal_coefficient", "equal_statistic"])
    .tab_spanner(label="Peso por preço", columns=["weighted_coefficient", "weighted_statistic"])
    .cols_label(
        weekday="Dia",
        equal_coefficient="Média",
        equal_statistic="t",
        weighted_coefficient="Média",
        weighted_statistic="t",
    )
    .tab_source_note(
        "Média do retorno do mercado em cada dia, com erros de Newey-West (7 defasagens). "
        f"Teste conjunto de médias iguais: p = {format_metric(joint['equal_p_value'], '.3f')} (peso igual) e "
        f"p = {format_metric(joint['weighted_p_value'], '.3f')} (peso por preço)."
    )
)
weekday_gt

# %% [markdown]
# ## Exportar tabelas LaTeX

# %%
tables = {
    "sale_seasons": seasons_gt,
    "sale_phases": phases_gt,
    "sale_events": events_gt,
    "sale_activity": activity_gt,
    "sale_rarity": rarity_gt,
    "weekday": weekday_gt,
}

write_outputs(tables, {}, args.tables, wide=WIDE_TABLES)
