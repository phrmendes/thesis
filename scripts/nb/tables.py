import marimo

__generated_with = "0.24.2"
app = marimo.App()


@app.cell
def imports():
    """Import the packages and the table code."""
    from pathlib import Path

    import marimo as mo
    from helpers.report import build_tables, write_tables

    return Path, build_tables, mo, write_tables


@app.cell
def options(Path, mo):
    """Read the command-line flags.

    Raises:
        SystemExit: The source folder does not exist.

    """
    cli = mo.cli_args()
    SOURCE_DIR = Path(cli.get("source") or "files")
    OUTPUT_DIR = Path(cli.get("output") or "tex/tables")

    if not SOURCE_DIR.exists():
        message = f"missing source folder {SOURCE_DIR}"
        raise SystemExit(message)

    return OUTPUT_DIR, SOURCE_DIR


@app.cell
def render_tables(SOURCE_DIR, build_tables):
    """Build every table from the parquet files."""
    tables = build_tables(SOURCE_DIR)

    return (tables,)


@app.cell
def write_files(OUTPUT_DIR, tables, write_tables):
    """Write one LaTeX file per table."""
    written = write_tables(tables, OUTPUT_DIR)

    return (written,)


@app.cell
def preview_tables(mo, tables):
    """Show the same tables inside marimo."""
    mo.vstack([mo.Html(table.as_raw_html()) for table in tables.values()])


if __name__ == "__main__":
    app.run()
