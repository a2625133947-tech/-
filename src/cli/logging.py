"""CLI-only diagnostics and third-party console noise control."""

from __future__ import annotations

from contextlib import contextmanager, redirect_stderr, redirect_stdout
import logging
import os
import warnings


def configure_logging(debug: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if debug else logging.ERROR,
        format="%(levelname)s %(name)s: %(message)s",
        force=True,
    )
    logging.captureWarnings(True)


@contextmanager
def quiet_runtime(debug: bool):
    """Keep provider prints and third-party warnings out of the normal CLI UI."""
    if debug:
        with warnings.catch_warnings():
            warnings.simplefilter("default")
            yield
        return
    with open(os.devnull, "w", encoding="utf-8") as sink:
        with redirect_stdout(sink), redirect_stderr(sink), warnings.catch_warnings():
            warnings.simplefilter("ignore")
            yield
