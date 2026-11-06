"""Homework Coach — Hermes plugin entrypoint."""
from __future__ import annotations

if __package__:  # loaded by Hermes as a package
    from .homework_coach.plugin import register
else:  # imported as a top-level module
    from homework_coach.plugin import register  # type: ignore[no-redef]

__all__ = ["register"]
