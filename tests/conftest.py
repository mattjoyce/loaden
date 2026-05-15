"""Shared fixtures for the loaden test suite."""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest


@pytest.fixture(autouse=True)
def restore_environ() -> Iterator[None]:
    """
    Snapshot os.environ before each test and restore it afterward.

    load_config mutates the real process environment (loaden_env files and the
    env: section). Without this, a variable set by one test leaks into the
    next and makes ordering-dependent failures. The restore runs as a finalizer
    so it survives test failures and exceptions.
    """
    snapshot = dict(os.environ)
    try:
        yield
    finally:
        os.environ.clear()
        os.environ.update(snapshot)
