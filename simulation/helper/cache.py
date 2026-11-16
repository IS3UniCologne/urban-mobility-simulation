"""Atomic writes for the derived artifacts cached under a dataset's ``.cache/`` directory."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

    import pandas as pd


def write_cache(frame: pd.DataFrame, path: Path, *, index: bool | None = None) -> None:
    """Write a frame to a parquet cache file, renaming it into place once complete.

    Parameters
    ----------
    frame : pandas.DataFrame
        Frame to cache. A GeoDataFrame is written as GeoParquet.
    path : Path
        Cache file path. Missing parent directories are created.
    index : bool or None
        Passed to ``to_parquet``. None stores a RangeIndex as metadata only.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        frame.to_parquet(partial, index=index)
        os.replace(partial, path)
    finally:
        partial.unlink(missing_ok=True)
