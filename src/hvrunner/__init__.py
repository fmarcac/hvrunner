"""hvrunner: terminal game library and Proton launcher."""

from __future__ import annotations

from .core.models import Game, HvrunnerError, favorite_key

__all__ = ["Game", "HvrunnerError", "favorite_key", "__version__"]

__version__ = "2.0.0"
