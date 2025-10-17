"""Simple computer opponents for Sa-Jin."""
from __future__ import annotations

import random
from typing import Optional, Tuple

from .game import GameState
from .pieces import PlayerSide, Position


def choose_random_action(game: GameState, side: PlayerSide) -> Tuple[str, Position, Optional[Tuple[str, str]], Optional[Position]]:
    """Pick a random legal action for the given side."""

    moves = game.legal_moves(side)
    if not moves:
        raise RuntimeError("No legal moves are available")
    piece_id, destination = random.choice(moves)
    resurrection_target: Optional[Position] = None
    candidate = game.resurrection_candidate(side)
    if candidate is not None:
        options = game.available_resurrection_positions(side)
        if not options:
            raise RuntimeError("No legal resurrection squares found")
        resurrection_target = random.choice(options)
    return piece_id, destination, None, resurrection_target
