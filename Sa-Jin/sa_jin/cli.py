"""Command line interface for playing Sa-Jin."""
from __future__ import annotations

import argparse
import random
from typing import Iterable, List, Optional, Tuple

from .ai import choose_random_action
from .game import GameState, Phase
from .pieces import BOARD_SIZE, Piece, PieceType, PlayerSide, Position

PIECE_NAME_MAP = {
    "triangle": PieceType.TRIANGLE,
    "t": PieceType.TRIANGLE,
    "rectangle": PieceType.RECTANGLE,
    "r": PieceType.RECTANGLE,
    "square": PieceType.SQUARE,
    "s": PieceType.SQUARE,
}


def piece_label(piece: Piece) -> str:
    prefix = "S" if piece.owner is PlayerSide.SOUTH else "N"
    symbol = piece.kind.value[0].upper() if piece.strong else piece.kind.value[0]
    return f"{prefix}{symbol}"


def render_board(game: GameState) -> str:
    rows: List[str] = []
    snapshot = game.board_snapshot()
    for row_index in reversed(range(BOARD_SIZE)):
        cells: List[str] = []
        for col_index in range(BOARD_SIZE):
            identifier = snapshot[row_index][col_index]
            if identifier:
                piece = game.board.get_piece(identifier)
                cells.append(piece_label(piece))
            else:
                cells.append(" .")
        rows.append(f"{row_index + 1} | {' '.join(cells)}")
    footer = "    " + " ".join(chr(ord("A") + idx) for idx in range(BOARD_SIZE))
    return "\n".join(rows + [footer])


def prompt_piece_type(remaining: Iterable[PieceType]) -> PieceType:
    remaining_names = {ptype.value for ptype in remaining}
    prompt = f"Choose a counter to place {sorted(remaining_names)}: "
    while True:
        response = input(prompt).strip().lower()
        if response in ("quit", "exit"):
            raise SystemExit
        piece_type = PIECE_NAME_MAP.get(response)
        if piece_type and piece_type in remaining:
            return piece_type
        print("Invalid counter type. Try again (triangle, rectangle, square).")


def prompt_position(message: str) -> Position:
    while True:
        response = input(message).strip()
        if response.lower() in {"quit", "exit"}:
            raise SystemExit
        try:
            return Position.from_algebraic(response)
        except ValueError as exc:
            print(exc)


def prompt_swap(game: GameState, side: PlayerSide) -> Optional[Tuple[str, str]]:
    response = input("Swap two counters? (y/N): ").strip().lower()
    if response not in {"y", "yes"}:
        return None
    identifiers = [piece.identifier for piece in game.board.alive_pieces() if piece.owner is side]
    print("Available counters:", ", ".join(identifiers))
    first = input("First counter id: ").strip()
    second = input("Second counter id: ").strip()
    if first.lower() in {"quit", "exit"} or second.lower() in {"quit", "exit"}:
        raise SystemExit
    return first, second


def prompt_resurrection(game: GameState, side: PlayerSide) -> Position:
    options = game.available_resurrection_positions(side)
    if not options:
        raise RuntimeError("No legal resurrection positions available")
    print("Resurrection available. Choose a square on your half of the board.")
    print("Allowed squares:", ", ".join(pos.algebraic for pos in options))
    while True:
        position = prompt_position("Resurrect at: ")
        if position in options:
            return position
        print("That square is not valid for resurrection.")


def handle_cpu_placement(game: GameState, side: PlayerSide) -> None:
    remaining = game.remaining_placements(side)
    if not remaining:
        raise RuntimeError("CPU has no pieces left to place")
    piece_type = random.choice(remaining)
    positions = game.placement_positions(side)
    if not positions:
        raise RuntimeError("CPU cannot find a valid placement square")
    position = random.choice(positions)
    game.place_piece(side, piece_type, position)
    print(f"CPU places {piece_type.value} at {position.algebraic}")


def handle_cpu_assignment(game: GameState, side: PlayerSide) -> None:
    pieces = sorted(
        [piece for piece in game.board.alive_pieces() if piece.owner is side],
        key=lambda p: (p.kind is not PieceType.TRIANGLE, p.kind is not PieceType.RECTANGLE),
    )
    strong = [p.identifier for p in pieces[:2]]
    game.assign_initial_strengths(side, strong)
    print(f"CPU sets {strong[0]} and {strong[1]} to strong.")


def handle_cpu_turn(game: GameState, side: PlayerSide) -> None:
    piece_id, destination, swap_pair, resurrection_position = choose_random_action(game, side)
    result = game.take_turn(side, piece_id, destination, swap_pair, resurrection_position)
    print(f"CPU moves {piece_id} to {destination.algebraic}")
    for captured in result.captures:
        print(f"CPU destroyed {captured.identifier}")
    if result.resurrected:
        print(f"CPU resurrected {result.resurrected.identifier} at {result.resurrected.position.algebraic}")
    elif result.needs_resurrection:
        options = game.available_resurrection_positions(side)
        if not options:
            raise RuntimeError("CPU has no legal resurrection squares")
        chosen = options[0]
        piece = game.complete_resurrection(side, chosen)
        print(f"CPU resurrected {piece.identifier} at {chosen.algebraic}")


def play_game(mode: str, cpu_side: Optional[PlayerSide]) -> None:
    game = GameState()
    print("Welcome to Sa-Jin: Three Strengths!")
    while game.phase is Phase.PLACEMENT:
        side = game.current_player
        print("\n" + render_board(game))
        if cpu_side is not None and side is cpu_side:
            handle_cpu_placement(game, side)
            continue
        remaining = game.remaining_placements(side)
        piece_type = prompt_piece_type(remaining)
        position = prompt_position("Place on square (e.g. D4): ")
        try:
            game.place_piece(side, piece_type, position)
        except ValueError as exc:
            print(f"Error: {exc}")
    print("\nPlacement complete. Assign strong sides.")
    while game.phase is Phase.ASSIGNMENT:
        side = game.current_player
        print("\n" + render_board(game))
        if cpu_side is not None and side is cpu_side:
            handle_cpu_assignment(game, side)
            continue
        pieces = [piece.identifier for piece in game.board.alive_pieces() if piece.owner is side]
        print("Your counters:", ", ".join(pieces))
        strong_input = input("Choose two counters to flip to strong (space separated): ").strip()
        if strong_input.lower() in {"quit", "exit"}:
            raise SystemExit
        strong_ids = strong_input.split()
        try:
            game.assign_initial_strengths(side, strong_ids)
        except ValueError as exc:
            print(f"Error: {exc}")
    print("\nGame start!")
    while game.phase is Phase.ACTIVE:
        side = game.current_player
        print("\n" + render_board(game))
        status = game.status_summary()
        print(f"Turn: {side.name}. Captures: {status['captures']}")
        if cpu_side is not None and side is cpu_side:
            handle_cpu_turn(game, side)
            continue
        identifiers = [piece.identifier for piece in game.board.alive_pieces() if piece.owner is side]
        print("Your counters:", ", ".join(identifiers))
        move_input = input("Move (e.g. S_triangle D4): ").strip()
        if move_input.lower() in {"quit", "exit"}:
            raise SystemExit
        try:
            move_id, dest_square = move_input.split()
        except ValueError:
            print("Please provide a counter id and a destination square.")
            continue
        try:
            destination = Position.from_algebraic(dest_square)
        except ValueError as exc:
            print(f"Error: {exc}")
            continue
        try:
            swap_pair = prompt_swap(game, side)
            result = game.take_turn(side, move_id, destination, swap_pair)
            if result.needs_resurrection:
                resurrection_position = prompt_resurrection(game, side)
                piece = game.complete_resurrection(side, resurrection_position)
                print(f"Resurrected {piece.identifier} at {piece.position.algebraic}.")
        except ValueError as exc:
            print(f"Error: {exc}")
            continue
        for captured in result.captures:
            print(f"You destroyed {captured.identifier}!")
        if result.resurrected:
            print(
                f"{result.resurrected.identifier} returned on {result.resurrected.position.algebraic}."
            )
    if game.phase is Phase.GAME_OVER:
        print("\n" + render_board(game))
        winner = game.winner
        if winner is None:
            print("The game ended without a winner.")
        else:
            print(f"{winner.name} wins by destroying two counters!")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Play the Sa-Jin board game.")
    parser.add_argument(
        "--mode",
        choices=["pvp", "cpu"],
        default="cpu",
        help="Select 2-player hot-seat (pvp) or versus CPU (cpu).",
    )
    parser.add_argument(
        "--cpu-side",
        choices=["south", "north"],
        default="north",
        help="When playing against the CPU, choose which side it controls.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    cpu_side: Optional[PlayerSide] = None
    if args.mode == "cpu":
        cpu_side = PlayerSide.SOUTH if args.cpu_side == "south" else PlayerSide.NORTH
    play_game(args.mode, cpu_side)


if __name__ == "__main__":
    main()
