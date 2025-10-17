"""Piece definitions and attack range helpers for Sa-Jin."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable, Optional, Set, Tuple

BOARD_SIZE = 8


class PlayerSide(Enum):
    """Logical orientation for a player on the board."""

    SOUTH = 0  # rows increase when moving forward
    NORTH = 1  # rows decrease when moving forward

    @property
    def forward_step(self) -> int:
        return 1 if self is PlayerSide.SOUTH else -1

    @property
    def home_rows(self) -> range:
        """Return the rows considered this player's half of the board."""

        if self is PlayerSide.SOUTH:
            return range(0, BOARD_SIZE // 2)
        return range(BOARD_SIZE // 2, BOARD_SIZE)

    @property
    def enemy_home_row(self) -> int:
        return BOARD_SIZE - 1 if self is PlayerSide.SOUTH else 0


class PieceType(Enum):
    TRIANGLE = "triangle"
    RECTANGLE = "rectangle"
    SQUARE = "square"


@dataclass(frozen=True)
class Position:
    row: int
    col: int

    def __post_init__(self) -> None:
        if not (0 <= self.row < BOARD_SIZE and 0 <= self.col < BOARD_SIZE):
            raise ValueError(f"Position out of bounds: {self.row}, {self.col}")

    @property
    def algebraic(self) -> str:
        return f"{chr(ord('A') + self.col)}{self.row + 1}"

    @staticmethod
    def from_algebraic(name: str) -> "Position":
        if len(name) < 2:
            raise ValueError(f"Invalid coordinate {name!r}")
        column = ord(name[0].upper()) - ord("A")
        try:
            row = int(name[1:]) - 1
        except ValueError as exc:
            raise ValueError(f"Invalid coordinate {name!r}") from exc
        if not (0 <= column < BOARD_SIZE and 0 <= row < BOARD_SIZE):
            raise ValueError(f"Coordinate {name!r} is outside the board")
        return Position(row=row, col=column)

    def translate(self, d_row: int, d_col: int) -> Optional["Position"]:
        new_row = self.row + d_row
        new_col = self.col + d_col
        if 0 <= new_row < BOARD_SIZE and 0 <= new_col < BOARD_SIZE:
            return Position(new_row, new_col)
        return None


@dataclass
class Piece:
    """Represents a counter on the board."""

    identifier: str
    owner: PlayerSide
    kind: PieceType
    position: Position
    strong: bool = False
    alive: bool = True

    def flip(self) -> None:
        self.strong = not self.strong


def triangle_attack_positions(
    position: Position, owner: PlayerSide, occupied: Set[Tuple[int, int]]
) -> Set[Position]:
    """Return the attack positions for a triangle counter.

    The triangle projects forward in a widening cone. Any counter in the
    projection blocks positions further behind it along the same file.
    """

    results: Set[Position] = set()
    blocked_cols: Set[int] = set()
    direction = owner.forward_step
    for distance in range(1, BOARD_SIZE):
        row = position.row + distance * direction
        if not (0 <= row < BOARD_SIZE):
            break
        width = distance * 2 + 1
        start_col = position.col - distance
        for offset in range(width):
            col = start_col + offset
            if not (0 <= col < BOARD_SIZE):
                continue
            if col in blocked_cols:
                continue
            target = Position(row, col)
            results.add(target)
            if (row, col) in occupied:
                blocked_cols.add(col)
    return results


def rectangle_attack_positions(
    position: Position, owner: PlayerSide, occupied: Set[Tuple[int, int]]
) -> Set[Position]:
    """Return the attack positions for a rectangle counter."""

    results: Set[Position] = set()
    # forward direction
    for step in range(1, 8):
        row = position.row + owner.forward_step * step
        if not (0 <= row < BOARD_SIZE):
            break
        target = Position(row, position.col)
        results.add(target)
        if (row, position.col) in occupied:
            break
    # backward direction
    for step in range(1, 8):
        row = position.row - owner.forward_step * step
        if not (0 <= row < BOARD_SIZE):
            break
        target = Position(row, position.col)
        results.add(target)
        if (row, position.col) in occupied:
            break
    return results


def square_attack_positions(
    position: Position, owner: PlayerSide, occupied: Set[Tuple[int, int]]
) -> Set[Position]:
    """Return the attack positions for a square counter."""

    results: Set[Position] = set()
    max_radius = 2
    for d_row in range(-max_radius, max_radius + 1):
        for d_col in range(-max_radius, max_radius + 1):
            if d_row == 0 and d_col == 0:
                continue
            if abs(d_row) + abs(d_col) > max_radius + 1:
                # trim the corners a little to keep range compact
                continue
            target = position.translate(d_row, d_col)
            if target is not None:
                results.add(target)
    return results


def attack_positions_for(
    piece: Piece, occupied: Set[Tuple[int, int]]
) -> Set[Position]:
    if piece.kind is PieceType.TRIANGLE:
        return triangle_attack_positions(piece.position, piece.owner, occupied)
    if piece.kind is PieceType.RECTANGLE:
        return rectangle_attack_positions(piece.position, piece.owner, occupied)
    return square_attack_positions(piece.position, piece.owner, occupied)


def iter_half_board(side: PlayerSide) -> Iterable[Position]:
    """Yield all positions on the specified player's half of the board."""

    rows = side.home_rows
    for row in rows:
        for col in range(BOARD_SIZE):
            yield Position(row=row, col=col)
