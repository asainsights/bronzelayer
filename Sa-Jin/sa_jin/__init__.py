"""Sa-Jin game package."""

from .game import GameState, PlayerSide
from .cli import main as cli_main

__all__ = ["GameState", "PlayerSide", "cli_main"]
