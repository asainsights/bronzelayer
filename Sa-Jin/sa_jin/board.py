"""Game board implementation for Sa-Jin."""
from __future__ import annotations

from typing import Dict, Iterable, Optional

from .pieces import Piece, PlayerSide, Position


class Board:
    """Represents the 8x8 board and piece placement."""

    def __init__(self) -> None:
        self._pieces: Dict[str, Piece] = {}

    # --- piece collections -------------------------------------------------
    def pieces(self) -> Iterable[Piece]:
        return list(self._pieces.values())

    def alive_pieces(self) -> Iterable[Piece]:
        return [piece for piece in self._pieces.values() if piece.alive]

    def pieces_for_player(self, side: PlayerSide) -> Iterable[Piece]:
        return [p for p in self.alive_pieces() if p.owner is side]

    def get_piece(self, identifier: str) -> Piece:
        return self._pieces[identifier]

    def piece_at(self, position: Position) -> Optional[Piece]:
        for piece in self.alive_pieces():
            if piece.position == position:
                return piece
        return None

    # --- occupancy ---------------------------------------------------------
    def is_occupied(self, position: Position) -> bool:
        return self.piece_at(position) is not None

    def occupied_coordinates(self) -> set[tuple[int, int]]:
        return {(p.position.row, p.position.col) for p in self.alive_pieces()}

    # --- mutating operations -----------------------------------------------
    def add_piece(self, piece: Piece) -> None:
        if piece.identifier in self._pieces:
            raise ValueError(f"Piece {piece.identifier} already exists")
        if self.is_occupied(piece.position):
            raise ValueError(f"Square {piece.position.algebraic} already occupied")
        self._pieces[piece.identifier] = piece

    def move_piece(self, identifier: str, new_position: Position) -> None:
        piece = self.get_piece(identifier)
        if not piece.alive:
            raise ValueError("Cannot move a captured piece")
        if self.is_occupied(new_position):
            raise ValueError(f"Square {new_position.algebraic} already occupied")
        piece.position = new_position

    def remove_piece(self, identifier: str) -> None:
        piece = self.get_piece(identifier)
        piece.alive = False

    def resurrect_piece(self, identifier: str, position: Position) -> None:
        piece = self.get_piece(identifier)
        if piece.alive:
            raise ValueError("Piece is already alive")
        if self.is_occupied(position):
            raise ValueError(f"Square {position.algebraic} already occupied")
        piece.position = position
        piece.alive = True
        piece.strong = False

    # --- utility -----------------------------------------------------------
    def copy(self) -> "Board":
        new_board = Board()
        for identifier, piece in self._pieces.items():
            new_piece = Piece(
                identifier=identifier,
                owner=piece.owner,
                kind=piece.kind,
                position=piece.position,
                strong=piece.strong,
                alive=piece.alive,
            )
            new_board._pieces[identifier] = new_piece
        return new_board
