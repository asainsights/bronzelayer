"""Pygame interface for playing Sa-Jin with a mouse."""
from __future__ import annotations

import argparse
import random
from collections import deque
from dataclasses import dataclass
from typing import Callable, Deque, Iterable, List, Optional, Tuple

try:
    import pygame
except ModuleNotFoundError as exc:  # pragma: no cover - import guard
    raise SystemExit(
        "pygame is required for the graphical interface. Install it with 'pip install pygame'."
    ) from exc

from .ai import choose_random_action
from .game import GameState, Phase, TurnResult
from .pieces import BOARD_SIZE, Piece, PieceType, PlayerSide, Position

# Window layout constants -----------------------------------------------------
CELL_SIZE = 80
BOARD_MARGIN = 32
PANEL_WIDTH = 260
BOARD_PIXEL_SIZE = CELL_SIZE * BOARD_SIZE
WINDOW_WIDTH = BOARD_PIXEL_SIZE + BOARD_MARGIN * 2 + PANEL_WIDTH
WINDOW_HEIGHT = BOARD_PIXEL_SIZE + BOARD_MARGIN * 2

# Colours --------------------------------------------------------------------
BOARD_LIGHT = (240, 217, 181)
BOARD_DARK = (181, 136, 99)
BOARD_BORDER = (70, 40, 30)
HIGHLIGHT_COLOUR = (255, 215, 0)
HOVER_COLOUR = (255, 255, 150)
TEXT_COLOUR = (30, 30, 30)
SOUTH_COLOUR = (66, 135, 245)
NORTH_COLOUR = (214, 69, 65)


@dataclass
class Button:
    """Simple clickable button."""

    rect: pygame.Rect
    label: str
    callback: Callable[[], None]
    enabled: bool = True

    def draw(self, surface: pygame.Surface, font: pygame.font.Font) -> None:
        colour = (210, 210, 210) if self.enabled else (160, 160, 160)
        pygame.draw.rect(surface, colour, self.rect)
        pygame.draw.rect(surface, (60, 60, 60), self.rect, 2)
        text = font.render(self.label, True, TEXT_COLOUR)
        text_rect = text.get_rect(center=self.rect.center)
        surface.blit(text, text_rect)

    def handle_click(self, position: Tuple[int, int]) -> bool:
        if self.enabled and self.rect.collidepoint(position):
            self.callback()
            return True
        return False


def lighten_colour(colour: Tuple[int, int, int]) -> Tuple[int, int, int]:
    r, g, b = colour
    return (min(255, r + 70), min(255, g + 70), min(255, b + 70))


class GameGUI:
    """Interactive pygame front-end for Sa-Jin."""

    def __init__(self, mode: str, cpu_side: Optional[PlayerSide]) -> None:
        pygame.init()
        pygame.display.set_caption("Sa-Jin: Three Strengths")
        self.screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("arial", 18)
        self.small_font = pygame.font.SysFont("arial", 16)
        self.title_font = pygame.font.SysFont("arial", 24, bold=True)

        self.game = GameState()
        self.mode = mode
        self.cpu_side = cpu_side

        self.running = True
        self.buttons: List[Button] = []
        self.log: Deque[str] = deque(maxlen=9)

        # Interaction state ---------------------------------------------------
        self.selected_piece_type: Optional[PieceType] = None
        self.assignment_selection: List[str] = []
        self.selected_piece_id: Optional[str] = None
        self.swap_mode = False
        self.swap_selection: List[str] = []
        self.pending_swap_pair: Optional[Tuple[str, str]] = None
        self.awaiting_resurrection = False
        self.resurrection_options: List[Position] = []

        self.push_message("Welcome to Sa-Jin: Three Strengths!")

    # ------------------------------------------------------------------
    def push_message(self, message: str) -> None:
        self.log.appendleft(message)

    # ------------------------------------------------------------------
    def board_rect(self) -> pygame.Rect:
        return pygame.Rect(BOARD_MARGIN, BOARD_MARGIN, BOARD_PIXEL_SIZE, BOARD_PIXEL_SIZE)

    def position_from_pixel(self, pos: Tuple[int, int]) -> Optional[Position]:
        board = self.board_rect()
        if not board.collidepoint(pos):
            return None
        rel_x = pos[0] - board.left
        rel_y = pos[1] - board.top
        col = rel_x // CELL_SIZE
        row_from_top = rel_y // CELL_SIZE
        row = BOARD_SIZE - 1 - row_from_top
        try:
            return Position(row=row, col=col)
        except ValueError:
            return None

    # ------------------------------------------------------------------
    def update_buttons(self) -> None:
        self.buttons.clear()
        panel_left = BOARD_MARGIN * 2 + BOARD_PIXEL_SIZE
        x = panel_left + 16
        y = BOARD_MARGIN + 160
        button_size = pygame.Rect(0, 0, PANEL_WIDTH - 32, 36)

        human_turn = self.cpu_side is None or self.game.current_player is not self.cpu_side

        if self.game.phase is Phase.PLACEMENT and human_turn:
            remaining = self.game.remaining_placements(self.game.current_player)
            for piece_type in remaining:
                rect = button_size.copy()
                rect.topleft = (x, y)
                label = f"Place {piece_type.value.title()}"
                self.buttons.append(
                    Button(rect=rect, label=label, callback=lambda p=piece_type: self.select_piece_type(p))
                )
                y += 44
        elif self.game.phase is Phase.ACTIVE and human_turn and not self.awaiting_resurrection:
            swap_rect = button_size.copy()
            swap_rect.topleft = (x, y)
            swap_label = "Choose swap pair" if not self.swap_mode else "Select counters..."
            self.buttons.append(Button(swap_rect, swap_label, self.start_swap_selection))
            y += 44
            clear_rect = button_size.copy()
            clear_rect.topleft = (x, y)
            self.buttons.append(Button(clear_rect, "Clear swap", self.clear_swap))
            y += 44
            cancel_rect = button_size.copy()
            cancel_rect.topleft = (x, y)
            self.buttons.append(Button(cancel_rect, "Deselect counter", self.clear_move_selection))

    # ------------------------------------------------------------------
    def select_piece_type(self, piece_type: PieceType) -> None:
        self.selected_piece_type = piece_type
        self.push_message(f"Selected {piece_type.value} for placement.")

    def start_swap_selection(self) -> None:
        if self.game.phase is not Phase.ACTIVE:
            return
        self.swap_mode = True
        self.swap_selection = []
        self.pending_swap_pair = None
        self.push_message("Click two of your counters to swap their sides this turn.")

    def clear_swap(self) -> None:
        self.swap_mode = False
        self.swap_selection = []
        self.pending_swap_pair = None
        self.push_message("Cleared swap selection.")

    def clear_move_selection(self) -> None:
        self.selected_piece_id = None

    # ------------------------------------------------------------------
    def handle_board_click(self, position: Position) -> None:
        if self.cpu_side is not None and self.game.current_player is self.cpu_side:
            return

        if self.awaiting_resurrection:
            if position in self.resurrection_options:
                piece = self.game.complete_resurrection(self.game.current_player, position)
                self.push_message(
                    f"Resurrected {piece.identifier} at {piece.position.algebraic} (weak)."
                )
                self.awaiting_resurrection = False
                self.resurrection_options = []
            else:
                self.push_message("Select a highlighted square to resurrect your counter.")
            return

        if self.game.phase is Phase.PLACEMENT:
            self.handle_placement_click(position)
        elif self.game.phase is Phase.ASSIGNMENT:
            self.handle_assignment_click(position)
        elif self.game.phase is Phase.ACTIVE:
            self.handle_active_click(position)

    # ------------------------------------------------------------------
    def handle_placement_click(self, position: Position) -> None:
        side = self.game.current_player
        if self.selected_piece_type is None:
            self.push_message("Select which counter to place using the buttons on the right.")
            return
        try:
            piece = self.game.place_piece(side, self.selected_piece_type, position)
        except ValueError as exc:
            self.push_message(str(exc))
            return
        self.push_message(f"Placed {piece.kind.value} at {position.algebraic} for {side.name}.")
        self.selected_piece_type = None

    def handle_assignment_click(self, position: Position) -> None:
        piece = self.game.board.piece_at(position)
        if piece is None or piece.owner is not self.game.current_player:
            self.push_message("Select your own counters to assign strength.")
            return
        identifier = piece.identifier
        if identifier in self.assignment_selection:
            self.assignment_selection.remove(identifier)
        else:
            if len(self.assignment_selection) >= 2:
                self.push_message("Only two counters can be selected as strong.")
                return
            self.assignment_selection.append(identifier)
        if len(self.assignment_selection) == 2:
            try:
                self.game.assign_initial_strengths(
                    self.game.current_player, list(self.assignment_selection)
                )
            except ValueError as exc:
                self.push_message(str(exc))
            else:
                strong_names = ", ".join(self.assignment_selection)
                self.push_message(f"Set {strong_names} to strong.")
            finally:
                self.assignment_selection.clear()

    def handle_active_click(self, position: Position) -> None:
        side = self.game.current_player
        piece = self.game.board.piece_at(position)

        if self.swap_mode:
            if piece is None or piece.owner is not side:
                self.push_message("Choose your own counters when selecting a swap pair.")
                return
            if piece.identifier in self.swap_selection:
                return
            self.swap_selection.append(piece.identifier)
            if len(self.swap_selection) == 2:
                self.pending_swap_pair = (self.swap_selection[0], self.swap_selection[1])
                self.swap_mode = False
                self.push_message(
                    f"Swap prepared for {self.pending_swap_pair[0]} and {self.pending_swap_pair[1]}."
                )
            return

        if piece is not None:
            if piece.owner is side:
                if self.selected_piece_id == piece.identifier:
                    self.selected_piece_id = None
                else:
                    self.selected_piece_id = piece.identifier
            else:
                self.push_message("That counter belongs to your opponent.")
            return

        if self.selected_piece_id is None:
            self.push_message("Select one of your counters before choosing a destination square.")
            return

        self.execute_move(position)

    # ------------------------------------------------------------------
    def execute_move(self, destination: Position) -> None:
        side = self.game.current_player
        try:
            result = self.game.take_turn(
                side,
                self.selected_piece_id,
                destination,
                self.pending_swap_pair,
            )
        except ValueError as exc:
            self.push_message(str(exc))
            return

        self.describe_turn_outcome(result)
        self.selected_piece_id = None
        self.swap_selection = []
        self.pending_swap_pair = None

        if result.needs_resurrection:
            self.awaiting_resurrection = True
            self.resurrection_options = self.game.available_resurrection_positions(side)
            if not self.resurrection_options:
                self.push_message("No legal squares available to resurrect your counter.")
            else:
                self.push_message("Choose a highlighted square to resurrect your counter.")

    # ------------------------------------------------------------------
    def describe_turn_outcome(self, result: TurnResult) -> None:
        for captured in result.captures:
            self.push_message(f"Destroyed {captured.identifier}!")
        if result.resurrected:
            piece = result.resurrected
            self.push_message(f"Resurrected {piece.identifier} at {piece.position.algebraic}.")
        if self.game.phase is Phase.GAME_OVER:
            if self.game.winner is None:
                self.push_message("The game ended without a winner.")
            else:
                self.push_message(f"{self.game.winner.name} wins the match!")

    # ------------------------------------------------------------------
    def run(self) -> None:
        while self.running:
            self.update_cpu()
            self.update_buttons()

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    if any(button.handle_click(event.pos) for button in self.buttons):
                        continue
                    position = self.position_from_pixel(event.pos)
                    if position is not None:
                        self.handle_board_click(position)

            self.draw()
            pygame.display.flip()
            self.clock.tick(30)

        pygame.quit()

    # ------------------------------------------------------------------
    def update_cpu(self) -> None:
        if self.cpu_side is None:
            return

        if self.game.phase is Phase.GAME_OVER:
            return

        side = self.cpu_side

        if self.game.current_player is not side:
            return

        if self.game.phase is Phase.PLACEMENT:
            self.cpu_place(side)
        elif self.game.phase is Phase.ASSIGNMENT:
            self.cpu_assign(side)
        elif self.game.phase is Phase.ACTIVE:
            self.cpu_move(side)

    def cpu_place(self, side: PlayerSide) -> None:
        remaining = self.game.remaining_placements(side)
        if not remaining:
            return
        piece_type = random.choice(remaining)
        positions = self.game.placement_positions(side)
        if not positions:
            return
        position = random.choice(positions)
        self.game.place_piece(side, piece_type, position)
        self.push_message(f"CPU placed {piece_type.value} at {position.algebraic}.")

    def cpu_assign(self, side: PlayerSide) -> None:
        pieces = [piece for piece in self.game.board.alive_pieces() if piece.owner is side]
        pieces.sort(
            key=lambda p: (p.kind is not PieceType.TRIANGLE, p.kind is not PieceType.RECTANGLE)
        )
        strong = [p.identifier for p in pieces[:2]]
        self.game.assign_initial_strengths(side, strong)
        self.push_message(f"CPU set {strong[0]} and {strong[1]} to strong.")

    def cpu_move(self, side: PlayerSide) -> None:
        piece_id, destination, swap_pair, resurrection = choose_random_action(self.game, side)
        result = self.game.take_turn(side, piece_id, destination, swap_pair, resurrection)
        self.push_message(f"CPU moved {piece_id} to {destination.algebraic}.")
        self.describe_turn_outcome(result)
        if result.needs_resurrection:
            self.resolve_resurrection(side)

    def resolve_resurrection(self, side: PlayerSide) -> None:
        options = self.game.available_resurrection_positions(side)
        if not options:
            self.awaiting_resurrection = False
            self.resurrection_options = []
            return
        position = options[0]
        piece = self.game.complete_resurrection(side, position)
        self.push_message(f"CPU resurrected {piece.identifier} at {position.algebraic}.")
        self.awaiting_resurrection = False
        self.resurrection_options = []

    # ------------------------------------------------------------------
    def draw(self) -> None:
        self.screen.fill((245, 239, 230))
        self.draw_board()
        self.draw_panel()

    def draw_board(self) -> None:
        board = self.board_rect()
        pygame.draw.rect(self.screen, BOARD_BORDER, board.inflate(4, 4), 0)
        for row in range(BOARD_SIZE):
            for col in range(BOARD_SIZE):
                x = board.left + col * CELL_SIZE
                y = board.top + (BOARD_SIZE - 1 - row) * CELL_SIZE
                colour = BOARD_LIGHT if (row + col) % 2 == 0 else BOARD_DARK
                pygame.draw.rect(self.screen, colour, pygame.Rect(x, y, CELL_SIZE, CELL_SIZE))

        self.draw_highlights(board)

        for piece in self.game.board.alive_pieces():
            self.draw_piece(piece, board)

        self.draw_coordinates(board)

    def draw_highlights(self, board: pygame.Rect) -> None:
        highlight_surface = pygame.Surface((CELL_SIZE, CELL_SIZE), pygame.SRCALPHA)
        highlight_surface.fill((*HIGHLIGHT_COLOUR, 70))
        hover_surface = pygame.Surface((CELL_SIZE, CELL_SIZE), pygame.SRCALPHA)
        hover_surface.fill((*HOVER_COLOUR, 60))

        if self.awaiting_resurrection:
            targets = self.resurrection_options
        elif self.game.phase is Phase.PLACEMENT and (
            self.cpu_side is None or self.game.current_player is not self.cpu_side
        ):
            targets = self.game.placement_positions(self.game.current_player)
        elif self.selected_piece_id:
            piece_moves = [
                pos
                for pid, pos in self.game.legal_moves(self.game.current_player)
                if pid == self.selected_piece_id
            ]
            targets = piece_moves
        else:
            targets = []

        for position in targets:
            x = board.left + position.col * CELL_SIZE
            y = board.top + (BOARD_SIZE - 1 - position.row) * CELL_SIZE
            self.screen.blit(highlight_surface, (x, y))

        if self.assignment_selection or self.swap_selection or self.selected_piece_id:
            selected_ids = set(self.assignment_selection)
            selected_ids.update(self.swap_selection)
            if self.selected_piece_id:
                selected_ids.add(self.selected_piece_id)
            for identifier in selected_ids:
                piece = self.game.board.get_piece(identifier)
                x = board.left + piece.position.col * CELL_SIZE
                y = board.top + (BOARD_SIZE - 1 - piece.position.row) * CELL_SIZE
                self.screen.blit(hover_surface, (x, y))

    def draw_piece(self, piece: Piece, board: pygame.Rect) -> None:
        base_x = board.left + piece.position.col * CELL_SIZE
        base_y = board.top + (BOARD_SIZE - 1 - piece.position.row) * CELL_SIZE
        rect = pygame.Rect(base_x, base_y, CELL_SIZE, CELL_SIZE)
        owner_colour = SOUTH_COLOUR if piece.owner is PlayerSide.SOUTH else NORTH_COLOUR
        fill_colour = owner_colour if piece.strong else lighten_colour(owner_colour)
        outline_colour = (255, 255, 255) if piece.strong else (40, 40, 40)

        if piece.kind is PieceType.TRIANGLE:
            self.draw_triangle(rect, fill_colour, outline_colour, piece.owner)
        elif piece.kind is PieceType.RECTANGLE:
            self.draw_rectangle_piece(rect, fill_colour, outline_colour)
        else:
            self.draw_square_piece(rect, fill_colour, outline_colour)

        label = piece.identifier.split("_")[-1][0].upper()
        text = self.small_font.render(label, True, outline_colour)
        text_rect = text.get_rect(center=rect.center)
        self.screen.blit(text, text_rect)

    def draw_triangle(
        self,
        rect: pygame.Rect,
        fill_colour: Tuple[int, int, int],
        outline_colour: Tuple[int, int, int],
        owner: PlayerSide,
    ) -> None:
        padding = 12
        if owner is PlayerSide.SOUTH:
            points = [
                (rect.centerx, rect.top + padding),
                (rect.left + padding, rect.bottom - padding),
                (rect.right - padding, rect.bottom - padding),
            ]
        else:
            points = [
                (rect.centerx, rect.bottom - padding),
                (rect.left + padding, rect.top + padding),
                (rect.right - padding, rect.top + padding),
            ]
        pygame.draw.polygon(self.screen, fill_colour, points)
        pygame.draw.polygon(self.screen, outline_colour, points, 3)

    def draw_rectangle_piece(
        self, rect: pygame.Rect, fill_colour: Tuple[int, int, int], outline_colour: Tuple[int, int, int]
    ) -> None:
        padding_x = 18
        inner = rect.inflate(-padding_x * 2, -12)
        pygame.draw.rect(self.screen, fill_colour, inner)
        pygame.draw.rect(self.screen, outline_colour, inner, 3)

    def draw_square_piece(
        self, rect: pygame.Rect, fill_colour: Tuple[int, int, int], outline_colour: Tuple[int, int, int]
    ) -> None:
        padding = 14
        points = [
            (rect.centerx, rect.top + padding),
            (rect.right - padding, rect.centery),
            (rect.centerx, rect.bottom - padding),
            (rect.left + padding, rect.centery),
        ]
        pygame.draw.polygon(self.screen, fill_colour, points)
        pygame.draw.polygon(self.screen, outline_colour, points, 3)

    def draw_coordinates(self, board: pygame.Rect) -> None:
        for col in range(BOARD_SIZE):
            label = self.small_font.render(chr(ord("A") + col), True, TEXT_COLOUR)
            x = board.left + col * CELL_SIZE + CELL_SIZE // 2
            y = board.bottom + 8
            self.screen.blit(label, label.get_rect(center=(x, y)))
        for row in range(BOARD_SIZE):
            label = self.small_font.render(str(row + 1), True, TEXT_COLOUR)
            x = board.left - 16
            y = board.top + (BOARD_SIZE - 1 - row) * CELL_SIZE + CELL_SIZE // 2
            self.screen.blit(label, label.get_rect(center=(x, y)))

    def draw_panel(self) -> None:
        panel_left = BOARD_MARGIN * 2 + BOARD_PIXEL_SIZE
        panel_rect = pygame.Rect(panel_left, BOARD_MARGIN, PANEL_WIDTH, BOARD_PIXEL_SIZE)
        pygame.draw.rect(self.screen, (230, 230, 230), panel_rect)
        pygame.draw.rect(self.screen, (120, 120, 120), panel_rect, 2)

        title = self.title_font.render("Game Info", True, TEXT_COLOUR)
        self.screen.blit(title, (panel_left + 16, BOARD_MARGIN + 12))

        status_lines = list(self.status_lines())
        y = BOARD_MARGIN + 52
        for line in status_lines:
            text = self.small_font.render(line, True, TEXT_COLOUR)
            self.screen.blit(text, (panel_left + 16, y))
            y += 20

        log_title = self.small_font.render("Recent events", True, TEXT_COLOUR)
        self.screen.blit(log_title, (panel_left + 16, BOARD_MARGIN + 120))
        y = BOARD_MARGIN + 144
        for message in list(self.log)[:8]:
            text = self.small_font.render(message, True, TEXT_COLOUR)
            self.screen.blit(text, (panel_left + 16, y))
            y += 20

        for button in self.buttons:
            button.draw(self.screen, self.small_font)

    def status_lines(self) -> Iterable[str]:
        yield f"Phase: {self.game.phase.name.title()}"
        if self.game.phase is not Phase.GAME_OVER:
            yield f"Current: {self.game.current_player.name.title()}"
        if self.game.phase is Phase.GAME_OVER and self.game.winner:
            yield f"Winner: {self.game.winner.name.title()}"
        captures = self.game.status_summary()["captures"]
        yield f"South captures: {captures['SOUTH']}"
        yield f"North captures: {captures['NORTH']}"
        if self.awaiting_resurrection:
            yield "Awaiting resurrection"
        if self.pending_swap_pair:
            yield f"Swap ready: {self.pending_swap_pair[0]} & {self.pending_swap_pair[1]}"
        if self.selected_piece_type is not None:
            yield f"Selected: {self.selected_piece_type.value}"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Play Sa-Jin using the graphical interface.")
    parser.add_argument(
        "--mode",
        choices=["pvp", "cpu"],
        default="cpu",
        help="Select human vs human hot-seat or versus CPU play.",
    )
    parser.add_argument(
        "--cpu-side",
        choices=["south", "north"],
        default="north",
        help="Which side the CPU controls when in CPU mode.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    cpu_side: Optional[PlayerSide] = None
    if args.mode == "cpu":
        cpu_side = PlayerSide.SOUTH if args.cpu_side == "south" else PlayerSide.NORTH
    gui = GameGUI(args.mode, cpu_side)
    gui.run()


if __name__ == "__main__":
    main()
