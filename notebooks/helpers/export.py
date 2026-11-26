from typing import TYPE_CHECKING

from great_tables import GT
from helpers.formatting import FONT_FAMILY, HELPER_PARAMETERS, write_latex_table
from IPython import get_ipython

if TYPE_CHECKING:
    from pathlib import Path

    from altair import TopLevelMixin


def enable_inline_table_styles() -> None:
    """Show each `GT` table with centered titles, the thesis font, and inline CSS.

    The call does nothing outside IPython, so a notebook still runs as a plain script.
    """
    shell = get_ipython()

    if shell is None:
        return

    def render_inline_html(table: GT) -> str:
        return table.tab_options(
            table_font_names=[FONT_FAMILY, "serif"], heading_align=HELPER_PARAMETERS.heading_align
        ).as_raw_html(inline_css=True)

    shell.display_formatter.formatters["text/html"].for_type(GT, render_inline_html)


def write_outputs(
    tables: dict[str, GT],
    charts: dict[str, TopLevelMixin],
    tables_directory: Path,
    images_directory: Path | None = None,
) -> None:
    """Write the tables and the PNG charts of one notebook and print one line for each file.

    Each table goes to `<tables>/<name>.tex`.

    Raises:
        ValueError: A chart has no images directory.

    """
    tables_directory.mkdir(parents=True, exist_ok=True)

    for name, table in tables.items():
        tex_path = tables_directory / f"{name}.tex"
        write_latex_table(table, tex_path)
        print(f"Written {tex_path}")

    for name, chart in charts.items():
        if images_directory is None:
            message = "a chart needs an images directory"
            raise ValueError(message)

        images_directory.mkdir(parents=True, exist_ok=True)
        path = images_directory / f"{name}.png"
        chart.save(path, scale_factor=HELPER_PARAMETERS.png_scale)
        print(f"Written {path}")
