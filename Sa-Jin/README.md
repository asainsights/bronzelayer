# Sa-Jin™ – Three Strengths

This folder contains a self-contained implementation of **Sa-Jin**, a chess-like board game played on an 8×8 board. The game recreates the rule set described in the original booklet and offers both hot-seat multiplayer and a simple CPU opponent.

## Project layout

```
Sa-Jin/
├── README.md           ← Game overview and instructions
└── sa_jin/
    ├── __init__.py
    ├── ai.py           ← Basic computer opponent
    ├── board.py        ← Board and piece storage logic
    ├── cli.py          ← Text-based interface for playing the game
    ├── gui.py          ← Mouse-driven interface powered by pygame
    ├── game.py         ← Core game rules and turn sequencing
    └── pieces.py       ← Piece definitions and attack range helpers
```

The core engine is pure Python. The optional graphical interface requires
[`pygame`](https://www.pygame.org/), which can be installed with `pip install pygame`.

## Running the game

From the repository root, move into the project folder and launch the command-line interface with:

```bash
cd Sa-Jin
python -m sa_jin.cli
```

By default the CPU controls the **North** side and moves second. You can switch to hot-seat multiplayer or let the CPU start instead:

```bash
# Hot-seat mode
python -m sa_jin.cli --mode pvp

# CPU plays the South side and moves first
python -m sa_jin.cli --mode cpu --cpu-side south
```

The interface walks you through the placement phase, initial strong/weak assignments, and each subsequent turn. Type `quit` at any prompt to leave the game.

### Graphical interface (mouse support)

Install pygame if you have not already:

```bash
pip install pygame
```

Start the graphical client:

```bash
python -m sa_jin.gui
```

Use the buttons on the right-hand panel to choose counters during placement, set up swaps, and monitor recent game events. Click squares on the board to place counters, select moves, and resolve resurrections. The graphical interface supports both hot-seat and CPU play using the same command-line options as the CLI:

```bash
# Hot-seat mode
python -m sa_jin.gui --mode pvp

# CPU plays the South side and moves first
python -m sa_jin.gui --mode cpu --cpu-side south
```

## Counter types and attack ranges

Each player controls three unique counters:

- **Triangle** – The power piece. Its attack extends forward in a widening triangle. The further the triangle is from the board edge, the deeper it projects. A counter standing in its path blocks any squares behind it in the same file.
- **Rectangle** – A long-range beam that attacks up to seven squares forward and backward. Any counter on the beam blocks squares behind it.
- **Square** – A short-range fighter that strikes within two steps in any direction, forming a compact radius around itself.

All counters move one square per turn in any direction.

Counters have two states:

- **Strong** counters can attack and be attacked.
- **Weak** counters cannot attack but are invulnerable. Weak counters still block beams and triangles, making them useful for defence.

At the start of play each side chooses two strong counters and one weak counter. If you lose a counter, the remaining two must immediately flip to their strong side.

## Winning the game

You destroy an opposing counter when the square it occupies is covered by the attack ranges of at least two of your strong counters. Destroy any two opposing counters to win.

If you have lost a counter, you can resurrect it by moving your remaining two counters to the row closest to your opponent. Once both stand on that row, place the resurrected counter on your half of the board (weak side up) to continue the fight.

## Playing tips

- Keep your triangle near the centre for the largest threat area.
- Use weak counters to shield allies or to block an opponent’s overlapping attack.
- The square excels up close; aim to advance it early.
- The rectangle’s long beam is perfect for covering lanes from a distance.
- Watch for resurrection opportunities to recover from an early loss.

Have fun balancing your three strengths!
