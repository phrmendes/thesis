import marimo

__generated_with = "0.24.2"
app = marimo.App()


@app.cell
def imports():
    """Import the packages and the chart code."""
    from pathlib import Path

    import marimo as mo
    from helpers.plots import build_charts, write_charts

    return Path, build_charts, mo, write_charts


@app.cell
def options(Path, mo):
    """Read the command-line flags.

    Raises:
        SystemExit: The prices file does not exist.

    """
    cli = mo.cli_args()
    PRICES_FILE = Path(cli.get("source") or "files/prices.parquet")
    MARKET_FILE = Path(cli.get("market") or "files/market.parquet")
    OUTPUT_DIR = Path(cli.get("output") or "images")

    if not PRICES_FILE.exists():
        message = f"missing prices file {PRICES_FILE}"
        raise SystemExit(message)

    return MARKET_FILE, OUTPUT_DIR, PRICES_FILE


@app.cell
def render_charts(MARKET_FILE, PRICES_FILE, build_charts):
    """Build the charts from the parquet files."""
    charts = build_charts(PRICES_FILE, MARKET_FILE)

    return (charts,)


@app.cell
def write_files(OUTPUT_DIR, charts, write_charts):
    """Write one SVG file per chart."""
    written = write_charts(charts, OUTPUT_DIR)

    return (written,)


@app.cell
def preview_charts(charts, mo):
    """Show the same charts inside marimo."""
    mo.vstack([mo.ui.altair_chart(chart) for chart in charts.values()])


if __name__ == "__main__":
    app.run()
