from typing import TYPE_CHECKING

import polars as pl

if TYPE_CHECKING:
    from datetime import date

EMBARGO_DAYS = 1


def walk_forward_splits(days: list[date], initial_days: int, step_days: int, horizon_days: int) -> pl.DataFrame:
    """Build expanding-window folds over the observed days, with an embargo between training and testing.

    The training window starts at the first day and grows by `step_days` in each fold.
    The testing window starts after the embargo and holds `horizon_days`.
    A fold needs a full testing window.

    Returns:
        One row per fold with the training and testing dates and day counts.

    """
    ordered = sorted(set(days))
    folds: list[dict[str, object]] = []
    training_end = initial_days

    while training_end + EMBARGO_DAYS + horizon_days <= len(ordered):
        test_start = training_end + EMBARGO_DAYS
        test_end = test_start + horizon_days
        folds.append(
            {
                "fold": len(folds) + 1,
                "train_start": ordered[0],
                "train_end": ordered[training_end - 1],
                "test_start": ordered[test_start],
                "test_end": ordered[test_end - 1],
                "train_days": training_end,
                "test_days": horizon_days,
            }
        )
        training_end += step_days

    return pl.DataFrame(folds)
