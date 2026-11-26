from os import environ
from pathlib import Path


def get_repo_root() -> Path:
    """Read the project root that devenv sets.

    Returns:
        The folder that holds `notebooks/` and `files/`.

    """
    return Path(environ["DEVENV_ROOT"])
