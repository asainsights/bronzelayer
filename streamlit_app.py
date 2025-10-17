"""Streamlit puzzle platformer starter kit.

This app gives you a tiny puzzle-platformer style adventure that runs in
Streamlit.  The logic is all written in Python so that new learners can read
through it and experiment.  The level is tile-based, which makes it easy to
swap in your own art or even design brand-new challenges by editing the
`LEVEL_BLUEPRINT` list.

The code is heavily commented to help younger coders follow along.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import streamlit as st
import streamlit.components.v1 as components

# -----------------------------------------------------------------------------
# 1.  BASIC SETUP
# -----------------------------------------------------------------------------

st.set_page_config(
    page_title="Mini Puzzle Platformer",
    page_icon="🕹️",
    layout="centered",
)

st.markdown(
    """
    <style>
    pre.game-board {
        font-size: 1.3rem;
        line-height: 1.1;
        margin: 0;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# A single tile on the map will be referenced using (x, y) coordinates where
# x is the column index and y is the row index.
Coord = Tuple[int, int]


@dataclass
class LevelPieces:
    """Holds the information we need to run one level."""

    base_grid: List[List[str]]
    player_start: Coord
    crate_positions: List[Coord]
    switch_positions: List[Coord]
    door_position: Coord
    key_position: Optional[Coord]


# The blueprint contains characters that we translate into game objects.
# Each character is explained in the README text that appears in the sidebar
# when the app runs.
LEVEL_BLUEPRINT = [
    "XXXXXXXXX",
    "XP..X..DX",
    "X..B....X",
    "X...S...X",
    "X..XK...X",
    "XXXXXXXXX",
]

# Friendly emojis for the default art set.  Young artists can swap any of these
# inside the Streamlit sidebar and the board will update instantly.
DEFAULT_ART: Dict[str, str] = {
    "player": "😀",
    "floor": "⬜",
    "wall": "🧱",
    "crate": "📦",
    "crate_on_switch": "✨📦",
    "switch": "🎛️",
    "door_closed": "🚪",
    "door_open": "🌟",
    "key": "🔑",
    "void": "⠀",
}

# -----------------------------------------------------------------------------
# 2.  HELPER FUNCTIONS
# -----------------------------------------------------------------------------


def parse_level(layout: List[str]) -> LevelPieces:
    """Convert the blueprint into structured data we can use in the game."""

    base_grid: List[List[str]] = []
    player_start: Optional[Coord] = None
    crate_positions: List[Coord] = []
    switch_positions: List[Coord] = []
    door_position: Optional[Coord] = None
    key_position: Optional[Coord] = None

    for y, row in enumerate(layout):
        base_row: List[str] = []
        for x, char in enumerate(row):
            if char == "P":
                player_start = (x, y)
                base_row.append(".")
            elif char == "B":
                crate_positions.append((x, y))
                base_row.append(".")
            elif char == "S":
                switch_positions.append((x, y))
                base_row.append("S")
            elif char == "D":
                door_position = (x, y)
                base_row.append(".")
            elif char == "K":
                key_position = (x, y)
                base_row.append(".")
            else:
                base_row.append(char)
        base_grid.append(base_row)

    if player_start is None:
        raise ValueError("The level blueprint must include a 'P' for the player start.")
    if door_position is None:
        raise ValueError("The level blueprint must include a 'D' for the exit door.")

    return LevelPieces(
        base_grid=base_grid,
        player_start=player_start,
        crate_positions=crate_positions,
        switch_positions=switch_positions,
        door_position=door_position,
        key_position=key_position,
    )


def reset_game_state(pieces: LevelPieces) -> None:
    """Store the starting state of the level inside Streamlit's session_state."""

    st.session_state.base_grid = deepcopy(pieces.base_grid)
    st.session_state.player_pos = pieces.player_start
    st.session_state.crates = set(pieces.crate_positions)
    st.session_state.switches = set(pieces.switch_positions)
    st.session_state.door_pos = pieces.door_position
    st.session_state.key_pos = pieces.key_position
    st.session_state.has_key = False
    st.session_state.door_open = False
    st.session_state.moves = 0
    st.session_state.game_over = False
    st.session_state.status_message = "Push the crate onto the glowing switch, grab the key, then head for the door!"

    if "art_assets" not in st.session_state:
        st.session_state.art_assets = deepcopy(DEFAULT_ART)


LEVEL_DATA = parse_level(LEVEL_BLUEPRINT)

if "base_grid" not in st.session_state:
    reset_game_state(LEVEL_DATA)


def tile_is_blocked(pos: Coord) -> bool:
    """Return True when the player or a crate cannot move onto the tile."""

    x, y = pos
    base_tile = st.session_state.base_grid[y][x]
    door_here = pos == st.session_state.door_pos

    if pos in st.session_state.crates:
        return True
    if door_here and not st.session_state.door_open:
        return True
    if base_tile == "X":
        return True
    return False


def update_door_state() -> None:
    """Open the exit when the puzzle is solved."""

    switch_complete = any(crate in st.session_state.switches for crate in st.session_state.crates)
    st.session_state.door_open = switch_complete and st.session_state.has_key


def move_player(dx: int, dy: int) -> None:
    """Attempt to move the player and handle crate pushing and puzzle logic."""

    if st.session_state.game_over:
        return

    px, py = st.session_state.player_pos
    target = (px + dx, py + dy)

    # Prevent moves that leave the map bounds.
    if not (0 <= target[0] < len(st.session_state.base_grid[0])):
        return
    if not (0 <= target[1] < len(st.session_state.base_grid)):
        return

    # If there is a crate in the way, try to push it.
    if target in st.session_state.crates:
        crate_destination = (target[0] + dx, target[1] + dy)
        if not (0 <= crate_destination[0] < len(st.session_state.base_grid[0])):
            return
        if not (0 <= crate_destination[1] < len(st.session_state.base_grid)):
            return
        if tile_is_blocked(crate_destination):
            return
        st.session_state.crates.remove(target)
        st.session_state.crates.add(crate_destination)

    # Check if the tile blocks the player (walls or closed door).
    if tile_is_blocked(target):
        return

    st.session_state.player_pos = target
    st.session_state.moves += 1

    # Pick up the key if we land on it.
    if st.session_state.key_pos and target == st.session_state.key_pos:
        st.session_state.has_key = True
        st.session_state.key_pos = None
        st.session_state.status_message = "Nice! You picked up the key. Now unlock that door."

    update_door_state()

    # Win condition: standing on the door while it is open.
    if target == st.session_state.door_pos and st.session_state.door_open:
        st.session_state.game_over = True
        st.session_state.status_message = "🚀 You escaped the puzzle room! Try designing your own next."
        st.balloons()


def render_board() -> str:
    """Build a multi-line string representation of the game board."""

    art = st.session_state.art_assets

    def prepare_art_lines(symbol: str) -> List[str]:
        lines = symbol.splitlines() or [symbol]
        width = max(len(line) for line in lines)
        return [line.ljust(width) for line in lines]

    prepared_art: Dict[str, List[str]] = {
        key: prepare_art_lines(value) for key, value in {**DEFAULT_ART, **art}.items()
    }
    max_height = max(len(lines) for lines in prepared_art.values())
    max_width = max(len(line) for lines in prepared_art.values() for line in lines)

    rendered_rows: List[str] = []
    for y, row in enumerate(st.session_state.base_grid):
        buffer_lines = [""] * max_height
        for x, base_tile in enumerate(row):
            pos = (x, y)
            if st.session_state.player_pos == pos:
                art_key = "player"
            elif pos in st.session_state.crates:
                art_key = "crate_on_switch" if pos in st.session_state.switches else "crate"
            elif st.session_state.key_pos and pos == st.session_state.key_pos:
                art_key = "key"
            elif pos == st.session_state.door_pos:
                art_key = "door_open" if st.session_state.door_open else "door_closed"
            else:
                if base_tile == "X":
                    art_key = "wall"
                elif base_tile == "S":
                    art_key = "switch"
                elif base_tile == ".":
                    art_key = "floor"
                else:
                    art_key = base_tile if base_tile in prepared_art else "void"

            tile_lines = prepared_art.get(art_key, prepared_art["void"])
            padded_tile = tile_lines + [" " * max_width] * (max_height - len(tile_lines))
            padded_tile = [line.ljust(max_width) for line in padded_tile]
            buffer_lines = [current + addition for current, addition in zip(buffer_lines, padded_tile)]

        rendered_rows.extend(buffer_lines)

    return "\n".join(rendered_rows)


# -----------------------------------------------------------------------------
# 3.  STREAMLIT PAGE LAYOUT
# -----------------------------------------------------------------------------

st.title("🧩 Mini Puzzle Platformer")

st.caption(
    "Push crates, step on switches, grab the key, and open the door. "
    "Edit the art in the sidebar to give the game your own look!"
)

with st.sidebar:
    st.header("🎮 How to Play")
    st.write(
        """
        * Use the arrow buttons or your keyboard's arrow keys to move.
        * Push the crate onto the glowing switch.
        * Snag the key.
        * When the door sparkles, step through it to win!
        """
    )

    st.subheader("🎨 Make Your Own Art")
    st.write(
        """
        Type any emoji, symbol, or even two-letter code you like. The board will
        refresh every time you change one of these boxes, so experiment freely!
        """
    )

    art_options = {
        "player": "Hero",
        "floor": "Floor",
        "wall": "Wall",
        "crate": "Crate",
        "crate_on_switch": "Crate on switch",
        "switch": "Switch",
        "door_closed": "Door closed",
        "door_open": "Door open",
        "key": "Key",
        "void": "Background",
    }

    for art_key, label in art_options.items():
        default_value = st.session_state.art_assets.get(art_key, DEFAULT_ART[art_key])
        if art_key == "player":
            user_value = st.text_area(
                label,
                value=default_value,
                key=f"art_{art_key}",
                height=120,
                help="Use multiple lines of emoji blocks (🟥🟦⬜) to draw pixel art!",
            )
        else:
            user_value = st.text_input(label, value=default_value, key=f"art_{art_key}")
        # Keep the default art if the input is cleared entirely.
        st.session_state.art_assets[art_key] = user_value or DEFAULT_ART[art_key]

    with st.expander("🖌️ Pixel Art Maker", expanded=False):
        st.write(
            """
            Pick colorful square emojis to paint a mini 3×3 hero. Press **Apply to hero**
            when you like the design. Tip: mix `⬛` for outlines and bright colors for
            eyes or clothes!
            """
        )

        pixel_palette = ["⬛", "⬜", "🟥", "🟧", "🟨", "🟩", "🟦", "🟪", "🟫", "⠀"]
        palette_labels = {
            "⬛": "⬛ Black",
            "⬜": "⬜ White",
            "🟥": "🟥 Red",
            "🟧": "🟧 Orange",
            "🟨": "🟨 Yellow",
            "🟩": "🟩 Green",
            "🟦": "🟦 Blue",
            "🟪": "🟪 Purple",
            "🟫": "🟫 Brown",
            "⠀": "(Blank)",
        }

        if "pixel_art_grid" not in st.session_state:
            st.session_state.pixel_art_grid = [
                ["⠀", "🟨", "⠀"],
                ["🟨", "⬜", "🟨"],
                ["🟧", "🟧", "🟧"],
            ]

        grid_rows = []
        for row_index in range(3):
            row_cols = []
            cols = st.columns(3)
            for col_index, col in enumerate(cols):
                key = f"pixel_{row_index}_{col_index}"
                current_value = st.session_state.pixel_art_grid[row_index][col_index]
                selected = col.selectbox(
                    "",
                    pixel_palette,
                    index=pixel_palette.index(current_value) if current_value in pixel_palette else 0,
                    key=key,
                    format_func=lambda emoji: palette_labels.get(emoji, emoji),
                )
                st.session_state.pixel_art_grid[row_index][col_index] = selected
                row_cols.append(selected)
            grid_rows.append(row_cols)

        if st.button("Apply to hero"):
            hero_art = "\n".join("".join(row) for row in grid_rows)
            st.session_state.art_assets["player"] = hero_art
            st.session_state["art_player"] = hero_art
            st.success("Custom pixel hero equipped! Try walking around to show it off.")

    st.divider()
    if st.button("🔄 Reset Level"):
        reset_game_state(LEVEL_DATA)

    st.write(
        """
        Want more levels? Add new rows to `LEVEL_BLUEPRINT` and use the same
        letters:

        * `X` – wall
        * `.` – empty floor
        * `P` – player start
        * `B` – crate
        * `S` – switch
        * `D` – door (one per level)
        * `K` – key (optional)
        """
    )

# Status panel and board display.
status_col, board_col = st.columns([1, 2])

with status_col:
    st.subheader("Stats")
    st.metric("Moves", st.session_state.moves)
    st.metric("Has key", "✅" if st.session_state.has_key else "❌")
    st.metric("Door open", "✅" if st.session_state.door_open else "❌")
    st.write("\n")
    st.info(st.session_state.status_message)

with board_col:
    st.subheader("Stage 1: Switcheroo Station")
    st.markdown(
        f"<pre class='game-board'>{render_board()}</pre>",
        unsafe_allow_html=True,
    )

    # Invisible component that listens for keyboard arrow presses and
    # relays them back to Streamlit as component values we can read in Python.
    key_event = components.html(
        """
        <script>
        (function() {
            const Streamlit = window.parent.Streamlit;
            if (!Streamlit) {
                return;
            }

            const resetValue = () => Streamlit.setComponentValue("");

            Streamlit.setComponentReady?.();
            Streamlit.setFrameHeight?.(0);
            resetValue();

            const handledKeys = {
                ArrowUp: true,
                ArrowDown: true,
                ArrowLeft: true,
                ArrowRight: true,
            };

            window.addEventListener("keydown", (event) => {
                const activeTag = document.activeElement?.tagName;
                if (["INPUT", "TEXTAREA", "SELECT"].includes(activeTag)) {
                    return;
                }

                if (handledKeys[event.key]) {
                    event.preventDefault();
                    Streamlit.setComponentValue(event.key);
                    setTimeout(resetValue, 0);
                }
            });
        })();
        </script>
        """,
        height=0,
    )

    key_to_move = {
        "ArrowUp": (0, -1),
        "ArrowDown": (0, 1),
        "ArrowLeft": (-1, 0),
        "ArrowRight": (1, 0),
    }

    if key_event in key_to_move:
        dx, dy = key_to_move[key_event]
        move_player(dx, dy)

    # Movement buttons arranged like a D-pad.
    _, up_col, _ = st.columns(3)
    if up_col.button("⬆️ Up"):
        move_player(0, -1)

    left_col, down_col, right_col = st.columns(3)
    if left_col.button("⬅️ Left"):
        move_player(-1, 0)
    if down_col.button("⬇️ Down"):
        move_player(0, 1)
    if right_col.button("➡️ Right"):
        move_player(1, 0)


st.write("---")

st.markdown(
    """
    ### Next Steps for Creators
    * Swap the emojis for mini pixel art characters or colors you create.
    * Change the letters in `LEVEL_BLUEPRINT` to craft a brand-new challenge.
    * Add more crates and switches to create multi-step puzzles.
    * Feeling brave? Try giving the player health and add lava tiles!
    """
)
