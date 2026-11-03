import marimo

__generated_with = "0.24.2"
app = marimo.App()


@app.cell
def imports():
    """Import the packages and the model code."""
    from pathlib import Path

    import marimo as mo
    from helpers.fitting import write_predictions

    return Path, mo, write_predictions


@app.cell
def options(Path, mo):
    """Read the command-line flags.

    Raises:
        SystemExit: The dataset file does not exist.

    """
    cli = mo.cli_args()
    DATASET_FILE = Path(cli.get("dataset") or "files/dataset.parquet")
    OUTPUT_FILE = Path(cli.get("output") or "files/predictions.parquet")

    if not DATASET_FILE.exists():
        message = f"missing dataset {DATASET_FILE}"
        raise SystemExit(message)

    return DATASET_FILE, OUTPUT_FILE


@app.cell
def predict(DATASET_FILE, OUTPUT_FILE, write_predictions):
    """Run the model and write the predictions."""
    predictions = write_predictions(DATASET_FILE, OUTPUT_FILE)

    return (predictions,)


if __name__ == "__main__":
    app.run()
