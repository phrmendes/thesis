from IPython import get_ipython


def notebook_arguments() -> list[str] | None:
    """Choose the argument list that the notebook parser reads.

    Returns:
        An empty list inside a Jupyter kernel, so the kernel flags do not reach the parser, and null in a terminal.

    """
    return [] if get_ipython() is not None else None
