from typing import TYPE_CHECKING

from great_tables import GT
from helpers.formatting import write_latex_table
from IPython import get_ipython

if TYPE_CHECKING:
    from pathlib import Path

    from altair import TopLevelMixin


def inline_table_styles() -> None:
    """Show each `GT` table in a notebook with its CSS inlined as `style` attributes.

    The call does nothing outside IPython, so a notebook still runs as a plain script.
    """
    shell = get_ipython()

    if shell is None:
        return

    def inline_html(table: GT) -> str:
        return table.as_raw_html(inline_css=True)

    shell.display_formatter.formatters["text/html"].for_type(GT, inline_html)


def write_outputs(
    tables: dict[str, GT],
    charts: dict[str, TopLevelMixin],
    tables_directory: Path,
    images_directory: Path | None = None,
    wide: frozenset[str] = frozenset(),
) -> None:
    """Write the tables and the PNG charts of one notebook and print one line for each file.

    Each table goes to `<tables>/<name>.tex`.
    The tables named in `wide` shrink to the text width in LaTeX when they are wider.

    Raises:
        ValueError: A chart has no images directory.

    """
    tables_directory.mkdir(parents=True, exist_ok=True)

    for name, table in tables.items():
        tex_path = tables_directory / f"{name}.tex"
        write_latex_table(table, tex_path, wide=name in wide)
        print(f"Written {tex_path}")

    for name, chart in charts.items():
        if images_directory is None:
            message = "a chart needs an images directory"
            raise ValueError(message)

        images_directory.mkdir(parents=True, exist_ok=True)
        path = images_directory / f"{name}.png"
        chart.save(path, scale_factor=2.0)
        print(f"Written {path}")
