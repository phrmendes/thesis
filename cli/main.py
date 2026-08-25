from typer import Typer

from .data.main import app as data_app
from .eda.main import app as eda_app

app = Typer(context_settings={"help_option_names": ["-h", "--help"]})

for sub_app in (data_app, eda_app):
    app.add_typer(sub_app)
