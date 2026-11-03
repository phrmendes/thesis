import re
from typing import TYPE_CHECKING

import polars as pl
from great_tables import GT
from statsmodels.tsa.stattools import adfuller

if TYPE_CHECKING:
    from pathlib import Path

DEC_MARK = ","
SEP_MARK = "."
NUMBER_PATTERN = re.compile(r"-?\d+(?:\.\d+)?")
TABULAR_START = re.compile(r"\\begin\{tabular\*\}\{\\linewidth\}\{@\{\\extracolsep\{\\fill\}\}(?P<spec>[^}]*)\}")
FIT_WIDTH = r"\resizebox{\ifdim\width>\linewidth\linewidth\else\width\fi}{!}{"

LABEL_MAP = {"rest": "Restante", "overall": "Geral"}

RETURN_COLUMNS = [
    "mean_return",
    "median_return",
    "min_return",
    "max_return",
    "std_return",
    "negative_returns_std",
]

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

DYNAMICS_LABELS = {
    "market_mean_return": "Retorno semanal médio do mercado",
    "market_std_return": "Desvio padrão do retorno do mercado",
    **{f"market_lag_{lag}": f"Autocorrelação do mercado (defasagem {lag})" for lag in range(1, 5)},
    **{f"asset_lag_{lag}": f"Autocorrelação dentro dos itens (defasagem {lag})" for lag in range(1, 5)},
    "mean_market_correlation": "Correlação média dos itens com o mercado",
    "median_market_correlation": "Correlação mediana dos itens com o mercado",
}

DISTRIBUTION_LABELS = {"capped": "Limitado (±100%)", "raw": "Bruto"}

SOURCE_LABELS = {
    "composite": "Índice csgotrader (todos os itens)",
    "composite_800": "Índice csgotrader (preço ≥ US$ 800)",
    "buff": "BUFF (menor oferta)",
}

PERCENT_COLUMNS = ["mean", "std", "p01", "p05", "p50", "p95", "p99", "share_above_half"]

TABLE_SOURCE = r"Fonte: Elaboração própria."
CAPTION = re.compile(r"\\caption\*\{\s*\{\\large (?P<title>[^}]*)\}\s*\}")


INTEGER_SELECTION_COLUMNS = [
    "assets",
    "selected",
    "low_price",
    "few_observations",
    "no_training_data",
]

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

PORTFOLIO_LABELS = {
    "assets": "Itens",
    "weeks": "Semanas de teste",
    "sale_fee": "Taxa de venda (%)",
    "roi": "ROI",
    "sharpe": "Sharpe",
    "sortino": "Sortino",
}


def is_wider_than_the_text(name: str) -> bool:
    """Return whether the table is wider than the text, so it must shrink.

    Returns:
        True when the table is wider than the text.

    """
    return name in {"returns", "distribution", "selection", "sources"}


def pt_text(text: str) -> str:
    """Write the numbers of one text in pt-BR: dot for thousands, comma for decimals. Keep dates.

    Returns:
        The same text with pt-BR numbers.

    """
    if "/" in text:
        return text

    def convert(match: re.Match[str]) -> str:
        whole, _, fraction = match.group().partition(".")
        sign = "-" if whole.startswith("-") else ""
        grouped = f"{int(whole.lstrip('-')):,}".replace(",", SEP_MARK)
        return f"{sign}{grouped}{DEC_MARK}{fraction}" if fraction else f"{sign}{grouped}"

    return NUMBER_PATTERN.sub(convert, text)


def pt_values(frame: pl.DataFrame) -> pl.DataFrame:
    """Convert the metric_value column to pt-BR text.

    Returns:
        The frame with the text column.

    """
    return frame.with_columns(pl.col("metric_value").map_elements(pt_text, return_dtype=pl.String))


def bold_cell(cell: str) -> str:
    """Wrap one header cell in bold, keeping a multicolumn group valid.

    Returns:
        The cell with a bold font.

    """
    body = cell.strip()
    suffix = ""
    while body.endswith("&"):
        body = body[:-1].rstrip()
        suffix = " &" + suffix

    if not body or body.startswith("\\textbf"):
        return cell

    multicolumn = re.fullmatch(r"(\\multicolumn\{[^}]*\}\{[^}]*\})\{(.*)\}", body)
    if multicolumn:
        return f"{multicolumn.group(1)}{{\\textbf{{{multicolumn.group(2)}}}}}{suffix}"

    return f"\\textbf{{{body}}}{suffix}"


def bold_header(latex: str) -> str:
    """Write the column names of the table in bold, as ABNT asks.

    Returns:
        The LaTeX with a bold header row.

    """
    lines = latex.split("\n")
    header_rows = [
        index - 1
        for index, line in enumerate(lines)
        if line.startswith(("\\midrule\\addlinespace", "\\cmidrule")) and index > 0
    ]
    for position in header_rows:
        header = lines[position].rstrip()
        tail = ""
        if header.endswith("\\\\"):
            header = header[:-2].rstrip()
            tail = " \\\\"

        if lines[position].lstrip().startswith("\\textbf"):
            continue

        cells = [bold_cell(cell) for cell in header.split(" & ")]
        lines[position] = " & ".join(cells) + tail

    return "\n".join(lines)


def add_source(latex: str) -> str:
    """Add the source line under the table, as ABNT asks.

    Returns:
        The LaTeX with the source line.

    """
    marker = "\\end{tabular*}"
    if marker in latex:
        position = latex.index(marker) + len(marker)
    else:
        marker = "\\end{tabular}\n}"
        position = latex.index(marker) + len(marker)

    line = "\n\\par\\vspace{\\belowcaptionskip}\\footnotesize " + TABLE_SOURCE + "\\par"

    return latex[:position] + line + latex[position:]


def write_table(table: GT, path: Path, *, wide: bool = False) -> Path:
    """Write one great-tables table as LaTeX, numbered and with its source.

    Returns:
        The path of the written file.

    """
    latex = table.as_latex().replace("!t]", "H]", 1)
    if wide:
        if "\\begin{tabular*}" in latex:
            latex = TABULAR_START.sub(lambda match: f"{FIT_WIDTH}\n\\begin{{tabular}}{{{match['spec']}}}", latex)
            latex = latex.replace("\\end{tabular*}", "\\end{tabular}\n}")
        else:
            latex = latex.replace("\\begin{tabular}", FIT_WIDTH + "\n\\begin{tabular}", 1)
            latex = latex.replace("\\end{tabular}", "\\end{tabular}\n}", 1)

    label = f"\\label{{tab:{path.stem}}}"
    latex = CAPTION.sub(lambda match: f"\\caption{{{match['title']}}}{label}", latex)
    latex = bold_header(latex)
    latex = add_source(latex)

    path.write_text(encoding="utf-8", data=latex)
    return path


def coverage(source: Path) -> dict[str, GT]:
    """Build the coverage tables.

    Returns:
        The tables, keyed by table name.

    """
    daily = pt_values(
        pl.read_parquet(source / "coverage_daily.parquet").with_columns(pl.col("metric_name").replace(DAILY_LABELS))
    )
    items = pl.read_parquet(source / "coverage_items.parquet")
    selection = pl.read_parquet(source / "selection.parquet")

    return {
        "coverage_daily": (
            GT(daily)
            .tab_header(title="Cobertura Temporal — CS:GO")
            .cols_label(metric_name="Métrica", metric_value="Valor")
        ),
        "coverage_items": (
            GT(items)
            .tab_header(title="Persistência dos Itens — CS:GO")
            .fmt_integer(columns=["universe_assets", "selected_assets"], sep_mark=SEP_MARK)
            .cols_label(
                weeks_range="Semanas com preço",
                universe_assets="Itens (universo)",
                selected_assets="Itens selecionados",
            )
            .tab_source_note(
                "O universo conta todos os itens com preço positivo. A seleção usa só as semanas de treino."
            )
        ),
        "selection": (
            GT(selection)
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
        ),
    }


def quality(source: Path) -> dict[str, GT]:
    """Build the quality table.

    Returns:
        The tables, keyed by table name.

    """
    stats = pt_values(
        pl.read_parquet(source / "quality.parquet").with_columns(pl.col("metric_name").replace(METRIC_LABELS))
    )
    return {
        "quality": (
            GT(stats)
            .tab_header(title="Qualidade do Conjunto de Dados Limpo — CS:GO")
            .cols_label(metric_name="Métrica", metric_value="Valor")
        )
    }


def returns(source: Path) -> dict[str, GT]:
    """Build the return statistics table.

    Returns:
        The tables, keyed by table name.

    """
    frame = pl.read_parquet(source / "returns.parquet").with_columns(pl.col("name").replace(LABEL_MAP))
    table = (
        GT(frame)
        .tab_header(title="Estatísticas dos Retornos — Itens CS:GO")
        .fmt_percent(columns=RETURN_COLUMNS, decimals=2, sep_mark=SEP_MARK, dec_mark=DEC_MARK)
        .fmt_number(
            columns=["n_weeks"],
            rows=list(range(len(frame) - 2)),
            decimals=0,
            sep_mark=SEP_MARK,
            dec_mark=DEC_MARK,
        )
        .fmt_number(
            columns=["n_weeks"],
            rows=[len(frame) - 2, len(frame) - 1],
            decimals=1,
            sep_mark=SEP_MARK,
            dec_mark=DEC_MARK,
        )
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

    return {"returns": table}


def distribution(source: Path) -> dict[str, GT]:
    """Build the return distribution table.

    Returns:
        The tables, keyed by table name.

    """
    frame = pl.read_parquet(source / "distribution.parquet").with_columns(pl.col("label").replace(DISTRIBUTION_LABELS))
    table = (
        GT(frame)
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
    return {"distribution": table}


def adf_row(label: str, values: list[float]) -> dict[str, str]:
    """Run an augmented Dickey-Fuller test and return one table row.

    Returns:
        One row of the dynamics table.

    """
    statistic, p_value, *_ = adfuller(values, autolag="AIC")
    return {"metric_name": label, "metric_value": f"{statistic:.2f} (p = {p_value:.3f})"}


def dynamics(source: Path) -> dict[str, GT]:
    """Build the market dynamics table.

    Returns:
        The tables, keyed by table name.

    """
    frame = pl.read_parquet(source / "dynamics.parquet").with_columns(pl.col("metric_name").replace(DYNAMICS_LABELS))
    market = pl.read_parquet(source / "market.parquet")
    tests = pl.DataFrame(
        [
            adf_row("Teste ADF: log do índice do mercado", market["market_index"].log().to_list()),
            adf_row("Teste ADF: retorno do mercado", market["market_return"].to_list()),
        ]
    )

    table = (
        GT(pt_values(pl.concat([frame, tests])))
        .tab_header(title="Dinâmica do Mercado — CS:GO")
        .cols_label(metric_name="Métrica", metric_value="Valor")
        .tab_source_note(
            "Mercado: média simples dos retornos semanais limitados. "
            "Correlação: itens com 100 semanas ou mais. ADF: estatística e p-valor. "
            "A autocorrelação negativa dentro dos itens pode refletir ruído no preço, não efeito de mercado."
        )
    )

    return {"dynamics": table}


def sources(source: Path) -> dict[str, GT]:
    """Build the source comparison table.

    Returns:
        The tables, keyed by table name.

    """
    frame = pl.read_parquet(source / "sources.parquet").with_columns(pl.col("source").replace(SOURCE_LABELS))
    table = (
        GT(frame)
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

    return {"sources": table}


def portfolio(source: Path) -> dict[str, GT]:
    """Build the portfolio table.

    Returns:
        The tables, keyed by table name.

    """
    frame = pt_values(
        pl.read_parquet(source / "portfolio.parquet").with_columns(pl.col("metric_name").replace(PORTFOLIO_LABELS))
    )

    table = (
        GT(frame)
        .tab_header(title="Carteira de Compra e Retenção — CS:GO")
        .cols_label(metric_name="Métrica", metric_value="Valor")
        .tab_source_note(
            "Carteira igualmente ponderada nas semanas de treino, sem rebalanceamento. "
            "Taxa de venda de 15% na última semana (5% Steam e 10% do jogo). "
            "Razões semanais com taxa livre de risco zero. "
            "Sortino: média sobre o DP das semanas negativas."
        )
    )

    return {"portfolio": table}


def activity(source: Path) -> dict[str, GT]:
    """Build the activity table.

    Returns:
        The tables, keyed by table name.

    """
    frame = pl.read_parquet(source / "activity.parquet")
    table = (
        GT(frame)
        .tab_header(title="Dias com Venda na Steam por Semana — CS:GO")
        .fmt_integer(columns=["item_weeks"], sep_mark=SEP_MARK)
        .cols_label(active_bucket="Dias com preço de 24 horas", item_weeks="Itens-semana")
        .tab_source_note(
            "Um dia com preço de 24 horas indica venda na Steam naquele dia. Serve como medida indireta de liquidez."
        )
    )

    return {"activity": table}


def build_tables(source: Path) -> dict[str, GT]:
    """Apply every builder to the source folder and merge the tables.

    Returns:
        Every table, keyed by table name.

    """
    builders = (coverage, quality, returns, distribution, dynamics, sources, activity, portfolio)
    return {name: table for builder in builders for name, table in builder(source).items()}


def write_tables(tables: dict[str, GT], output: Path) -> list[Path]:
    """Write every table as a LaTeX file and return the paths.

    Returns:
        The path of each written file.

    """
    output.mkdir(parents=True, exist_ok=True)
    written = []

    for name, table in tables.items():
        path = output / f"{name}.tex"
        print(f"Written {write_table(table, path, wide=is_wider_than_the_text(name))}")
        written.append(path)

    return written
