"""Game state management for Sa-Jin."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import Dict, List, Optional, Sequence, Tuple

from .board import Board
from .pieces import (
    BOARD_SIZE,
    Piece,
    PieceType,
    PlayerSide,
    Position,
    attack_positions_for,
    iter_half_board,
)


class Phase(Enum):
    PLACEMENT = auto()
    ASSIGNMENT = auto()
    ACTIVE = auto()
    GAME_OVER = auto()


@dataclass
class TurnResult:
    captures: List[Piece]
    resurrected: Optional[Piece] = None
    needs_resurrection: bool = False


class GameState:
    """Container for the rules and flow of a Sa-Jin match."""

    def __init__(self, starting_player: PlayerSide = PlayerSide.SOUTH) -> None:
        self.board = Board()
        self.starting_player = starting_player
        self.current_player = starting_player
        self.phase = Phase.PLACEMENT
        self._placements_remaining: Dict[PlayerSide, List[PieceType]] = {
            PlayerSide.SOUTH: [PieceType.TRIANGLE, PieceType.RECTANGLE, PieceType.SQUARE],
            PlayerSide.NORTH: [PieceType.TRIANGLE, PieceType.RECTANGLE, PieceType.SQUARE],
        }
        self._initial_strength_assigned: Dict[PlayerSide, bool] = {
            PlayerSide.SOUTH: False,
            PlayerSide.NORTH: False,
        }
        self._captures: Dict[PlayerSide, int] = {
            PlayerSide.SOUTH: 0,
            PlayerSide.NORTH: 0,
        }
        self.winner: Optional[PlayerSide] = None
        self._awaiting_resurrection: Optional[Piece] = None

    # ------------------------------------------------------------------
    def other_player(self, side: PlayerSide) -> PlayerSide:
        return PlayerSide.NORTH if side is PlayerSide.SOUTH else PlayerSide.SOUTH

    # ------------------------------------------------------------------
    def _validate_alignment(self, position: Position) -> None:
        for piece in self.board.alive_pieces():
            if piece.position.row == position.row or piece.position.col == position.col:
                raise ValueError(
                    "Counters cannot share the same row or column during placement"
                )

    def _validate_half(self, side: PlayerSide, position: Position) -> None:
        if position.row not in side.home_rows:
            raise ValueError("Counter must be placed on your half of the board")

    def _identifier_for(self, side: PlayerSide, kind: PieceType) -> str:
        prefix = "S" if side is PlayerSide.SOUTH else "N"
        return f"{prefix}_{kind.value}"

    def _pieces_for_side(self, side: PlayerSide) -> List[Piece]:
        return [p for p in self.board.alive_pieces() if p.owner is side]

    def _all_pieces_for_side(self, side: PlayerSide) -> List[Piece]:
        return [p for p in self.board.pieces() if p.owner is side]

    def remaining_placements(self, side: PlayerSide) -> List[PieceType]:
        return list(self._placements_remaining[side])

    def placement_positions(self, side: PlayerSide) -> List[Position]:
        if self.phase is not Phase.PLACEMENT:
            return []
        options: List[Position] = []
        for position in iter_half_board(side):
            if position.row not in side.home_rows:
                continue
            if self.board.is_occupied(position):
                continue
            try:
                self._validate_alignment(position)
            except ValueError:
                continue
            options.append(position)
        return options

    def _enforce_strength_requirements(self, side: PlayerSide) -> None:
        alive = [p for p in self.board.alive_pieces() if p.owner is side]
        strong_count = sum(1 for p in alive if p.strong)
        required = min(len(alive), 2)
        if strong_count < required:
            raise ValueError("At least two counters must be on their strong side")

    # ------------------------------------------------------------------
    def place_piece(self, side: PlayerSide, kind: PieceType, position: Position) -> Piece:
        if self.phase is not Phase.PLACEMENT:
            raise ValueError("Pieces can only be placed during the placement phase")
        if side is not self.current_player:
            raise ValueError("It is not this player's placement turn")
        remaining = self._placements_remaining[side]
        if kind not in remaining:
            raise ValueError("This piece has already been placed")
        self._validate_half(side, position)
        self._validate_alignment(position)
        identifier = self._identifier_for(side, kind)
        piece = Piece(identifier=identifier, owner=side, kind=kind, position=position)
        self.board.add_piece(piece)
        remaining.remove(kind)
        # update turn order
        other = self.other_player(side)
        if self._placements_remaining[other]:
            self.current_player = other
        elif remaining:
            # opponent done but this player still has pieces
            self.current_player = side
        else:
            # both done placing
            self.phase = Phase.ASSIGNMENT
            self.current_player = side
        return piece

    def assign_initial_strengths(
        self, side: PlayerSide, strong_identifiers: Sequence[str]
    ) -> None:
        if self.phase is not Phase.ASSIGNMENT:
            raise ValueError("Initial strengths can only be assigned after placement")
        if self._initial_strength_assigned[side]:
            raise ValueError("This player has already assigned strengths")
        pieces = self._pieces_for_side(side)
        if len(pieces) != 3:
            raise ValueError("All three counters must be on the board to assign strength")
        strong_set = set(strong_identifiers)
        if len(strong_set) != 2:
            raise ValueError("Exactly two counters must be designated strong")
        for piece in pieces:
            piece.strong = piece.identifier in strong_set
        self._initial_strength_assigned[side] = True
        if all(self._initial_strength_assigned.values()):
            self.phase = Phase.ACTIVE
            self.current_player = self.starting_player

    # ------------------------------------------------------------------
    def _validate_move(self, piece: Piece, destination: Position) -> None:
        if not piece.alive:
            raise ValueError("Cannot move a captured counter")
        if self.board.is_occupied(destination):
            raise ValueError("Destination square is occupied")
        d_row = abs(piece.position.row - destination.row)
        d_col = abs(piece.position.col - destination.col)
        if d_row == 0 and d_col == 0:
            raise ValueError("A counter must move at least one square")
        if d_row > 1 or d_col > 1:
            raise ValueError("Counters move one square in any direction")

    def _swap_strengths(self, side: PlayerSide, swap_pair: Optional[Tuple[str, str]]) -> None:
        if not swap_pair:
            return
        first_id, second_id = swap_pair
        if first_id == second_id:
            raise ValueError("Cannot swap a counter with itself")
        pieces = {p.identifier: p for p in self._pieces_for_side(side)}
        try:
            first = pieces[first_id]
            second = pieces[second_id]
        except KeyError as exc:
            raise ValueError("Both counters in a swap must belong to the player") from exc
        first.strong, second.strong = second.strong, first.strong
        self._enforce_strength_requirements(side)

    def _resolve_captures(self, attacker: PlayerSide) -> List[Piece]:
        occupied = self.board.occupied_coordinates()
        coverage: Dict[Tuple[int, int], int] = {}
        for piece in self.board.alive_pieces():
            if piece.owner is not attacker or not piece.strong:
                continue
            for target in attack_positions_for(piece, occupied):
                key = (target.row, target.col)
                coverage[key] = coverage.get(key, 0) + 1
        captured: List[Piece] = []
        for piece in list(self.board.alive_pieces()):
            if piece.owner is attacker or not piece.strong:
                continue
            key = (piece.position.row, piece.position.col)
            if coverage.get(key, 0) >= 2:
                self.board.remove_piece(piece.identifier)
                captured.append(piece)
        for piece in captured:
            piece.strong = False
            defender = piece.owner
            self._captures[attacker] += 1
            remaining = self._pieces_for_side(defender)
            if len(remaining) == 2:
                for survivor in remaining:
                    survivor.strong = True
        if captured and self._captures[attacker] >= 2:
            self.phase = Phase.GAME_OVER
            self.winner = attacker
        return captured

    def _can_resurrect(self, side: PlayerSide) -> Optional[Piece]:
        lost = [p for p in self.board.pieces() if p.owner is side and not p.alive]
        if len(lost) != 1:
            return None
        survivors = self._pieces_for_side(side)
        if len(survivors) != 2:
            return None
        target_row = side.enemy_home_row
        if all(piece.position.row == target_row for piece in survivors):
            return lost[0]
        return None

    def _validate_resurrection_position(
        self, side: PlayerSide, position: Position
    ) -> None:
        self._validate_half(side, position)
        if self.board.is_occupied(position):
            raise ValueError("Cannot resurrect onto an occupied square")
        for piece in self.board.alive_pieces():
            if piece.position.row == position.row or piece.position.col == position.col:
                raise ValueError("Resurrected counter cannot align with another counter")

    def resurrection_candidate(self, side: PlayerSide) -> Optional[Piece]:
        return self._can_resurrect(side)

    def available_resurrection_positions(self, side: PlayerSide) -> List[Position]:
        if self._can_resurrect(side) is None:
            return []
        options: List[Position] = []
        for position in iter_half_board(side):
            try:
                self._validate_resurrection_position(side, position)
            except ValueError:
                continue
            options.append(position)
        return options

    def take_turn(
        self,
        side: PlayerSide,
        piece_id: str,
        destination: Position,
        swap_pair: Optional[Tuple[str, str]] = None,
        resurrection_position: Optional[Position] = None,
    ) -> TurnResult:
        if self.phase is not Phase.ACTIVE:
            raise ValueError("Cannot take a turn until the game has started")
        if self._awaiting_resurrection is not None:
            raise ValueError("A resurrection must be completed before taking another turn")
        if side is not self.current_player:
            raise ValueError("It is not this player's turn")
        piece = self.board.get_piece(piece_id)
        if piece.owner is not side:
            raise ValueError("You can only move your own counters")
        self._validate_move(piece, destination)
        self.board.move_piece(piece.identifier, destination)
        self._swap_strengths(side, swap_pair)
        captures = self._resolve_captures(side)
        resurrected_piece: Optional[Piece] = None
        needs_resurrection = False
        candidate = self._can_resurrect(side)
        if candidate is not None:
            if resurrection_position is None:
                self._awaiting_resurrection = candidate
                needs_resurrection = True
            else:
                self._validate_resurrection_position(side, resurrection_position)
                self.board.resurrect_piece(candidate.identifier, resurrection_position)
                resurrected_piece = self.board.get_piece(candidate.identifier)
        elif resurrection_position is not None:
            raise ValueError("A resurrection was requested but no counter can return")
        if not needs_resurrection and self.phase is Phase.ACTIVE:
            self.current_player = self.other_player(side)
        return TurnResult(
            captures=captures,
            resurrected=resurrected_piece,
            needs_resurrection=needs_resurrection,
        )

    def complete_resurrection(self, side: PlayerSide, position: Position) -> Piece:
        if self._awaiting_resurrection is None:
            raise ValueError("No resurrection is pending")
        candidate = self._awaiting_resurrection
        if candidate.owner is not side:
            raise ValueError("It is not this player's resurrection to resolve")
        self._validate_resurrection_position(side, position)
        self.board.resurrect_piece(candidate.identifier, position)
        piece = self.board.get_piece(candidate.identifier)
        self._awaiting_resurrection = None
        if self.phase is Phase.ACTIVE:
            self.current_player = self.other_player(side)
        return piece

    # ------------------------------------------------------------------
    def legal_moves(self, side: PlayerSide) -> List[Tuple[str, Position]]:
        moves: List[Tuple[str, Position]] = []
        for piece in self._pieces_for_side(side):
            for d_row in (-1, 0, 1):
                for d_col in (-1, 0, 1):
                    if d_row == 0 and d_col == 0:
                        continue
                    target = piece.position.translate(d_row, d_col)
                    if target is None:
                        continue
                    if self.board.is_occupied(target):
                        continue
                    moves.append((piece.identifier, target))
        return moves

    def status_summary(self) -> Dict[str, object]:
        return {
            "phase": self.phase.name,
            "current_player": self.current_player.name,
            "winner": self.winner.name if self.winner else None,
            "captures": {side.name: count for side, count in self._captures.items()},
        }

    def board_snapshot(self) -> List[List[Optional[str]]]:
        snapshot: List[List[Optional[str]]] = [
            [None for _ in range(BOARD_SIZE)] for _ in range(BOARD_SIZE)
        ]
        for piece in self.board.alive_pieces():
            snapshot[piece.position.row][piece.position.col] = piece.identifier
        return snapshot
