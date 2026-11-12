import re
from typing import TYPE_CHECKING

import polars as pl
from helpers.params import load_params

if TYPE_CHECKING:
    from datetime import date
    from pathlib import Path

    from great_tables import GT

DEC_MARK = ","
SEP_MARK = "."
TABLE_SOURCE = r"Fonte: Elaboração própria."
CAPTION = re.compile(r"\\caption\*\{\s*\{\\large (?P<title>[^}]*)\}\s*\}")
NUMBER_PATTERN = re.compile(r"-?\d+(?:\.\d+)?")
TABULAR_START = re.compile(r"\\begin\{tabular\*\}\{\\linewidth\}\{@\{\\extracolsep\{\\fill\}\}(?P<spec>[^}]*)\}")
FIT_WIDTH = r"\resizebox{\ifdim\width>\linewidth\linewidth\else\width\fi}{!}{"


def pt_number(match: re.Match[str]) -> str:
    """Write one matched number with a dot for thousands and a comma for decimals.

    Returns:
        The number in pt-BR.

    """
    whole, _, fraction = match.group().partition(".")
    sign = "-" if whole.startswith("-") else ""
    grouped = f"{int(whole.lstrip('-')):,}".replace(",", SEP_MARK)
    decimals = f"{DEC_MARK}{fraction}" if fraction else ""

    return f"{sign}{grouped}{decimals}"


def pt_text(text: str) -> str:
    """Write the numbers of one text in pt-BR: dot for thousands, comma for decimals. Keep dates.

    Returns:
        The same text with pt-BR numbers.

    """
    if "/" in text:
        return text

    return NUMBER_PATTERN.sub(pt_number, text)


def format_metric(value: float | date | None, spec: str) -> str:
    """Format one metric value with a format spec and write it in pt-BR.

    Returns:
        The pt-BR text, or "n/d" when the value is null.

    """
    if value is None:
        return "n/d"

    return pt_text(format(value, spec))


def cap_text() -> str:
    """Write the return cap as a percent in pt-BR.

    Returns:
        The cap, for example `500%`.

    """
    return format_metric(load_params()["clean"]["return_cap"], ".0%")


def metric_text_table(metrics: pl.DataFrame, labels: dict[str, str], formats: dict[str, str]) -> pl.DataFrame:
    """Turn a one-row metric frame into label and text rows, in the order of the labels.

    Returns:
        One row per label with the metric name and the formatted value.

    """
    record = metrics.row(0, named=True)
    names = [labels[name] for name in labels]
    values = [format_metric(record[name], formats[name]) for name in labels]

    return pl.DataFrame({"metric_name": names, "metric_value": values})


def split_trailing_ampersands(cell: str) -> tuple[str, str]:
    """Split a header cell into its text and its trailing column separators.

    Returns:
        The text without separators and the separators.

    """
    body = cell.strip()
    suffix = ""

    while body.endswith("&"):
        body = body[:-1].rstrip()
        suffix = " &" + suffix

    return body, suffix


def bold_cell(cell: str) -> str:
    """Wrap one header cell in bold, keeping a multicolumn group valid.

    Returns:
        The cell with a bold font.

    """
    body, suffix = split_trailing_ampersands(cell)

    if not body or body.startswith("\\textbf"):
        return cell

    multicolumn = re.fullmatch(r"(\\multicolumn\{[^}]*\}\{[^}]*\})\{(.*)\}", body)

    if multicolumn:
        return f"{multicolumn.group(1)}{{\\textbf{{{multicolumn.group(2)}}}}}{suffix}"

    return f"\\textbf{{{body}}}{suffix}"


def bold_line(line: str) -> str:
    """Write every cell of one header line in bold.

    Returns:
        The header line with bold cells.

    """
    if line.lstrip().startswith("\\textbf"):
        return line

    header = line.rstrip()
    row_end = ""

    if header.endswith("\\\\"):
        header = header[:-2].rstrip()
        row_end = " \\\\"

    cells = [bold_cell(cell) for cell in header.split(" & ")]

    return " & ".join(cells) + row_end


def header_line_positions(lines: list[str]) -> list[int]:
    """Find the lines that hold the column names, just above a header rule.

    Returns:
        The position of each header line.

    """
    rules = ("\\midrule\\addlinespace", "\\cmidrule")

    return [index - 1 for index, line in enumerate(lines) if index > 0 and line.startswith(rules)]


def bold_header(latex: str) -> str:
    """Write the column names of the table in bold, as ABNT asks.

    Returns:
        The LaTeX with a bold header row.

    """
    lines = latex.split("\n")

    for position in header_line_positions(lines):
        lines[position] = bold_line(lines[position])

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


def fit_to_text_width(latex: str) -> str:
    """Shrink the table to the text width when it is wider.

    Returns:
        The LaTeX with a resize box around the table.

    """
    if "\\begin{tabular*}" not in latex:
        boxed = latex.replace("\\begin{tabular}", FIT_WIDTH + "\n\\begin{tabular}", 1)

        return boxed.replace("\\end{tabular}", "\\end{tabular}\n}", 1)

    boxed = TABULAR_START.sub(lambda match: f"{FIT_WIDTH}\n\\begin{{tabular}}{{{match['spec']}}}", latex)

    return boxed.replace("\\end{tabular*}", "\\end{tabular}\n}")


def write_latex_table(table: GT, path: Path, *, wide: bool = False) -> Path:
    """Write one great-tables table as LaTeX, numbered and with its source.

    Returns:
        The path of the written file.

    """
    latex = table.as_latex().replace("!t]", "H]", 1)
    label = f"\\label{{tab:{path.stem}}}"

    if wide:
        latex = fit_to_text_width(latex)

    numbered = CAPTION.sub(lambda match: f"\\caption{{{match['title']}}}{label}", latex)
    path.write_text(encoding="utf-8", data=add_source(bold_header(numbered)))

    return path
