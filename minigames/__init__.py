# minigames/__init__.py
from __future__ import annotations

from typing import Dict

from .snake_duel import SnakeDuelGame
from .minesweeper_buff import MinesweeperBuffGame
from .solitaire_love import SolitaireLoveGame  

MINIGAMES: Dict[str, object] = {
    "mg1": SnakeDuelGame(),
    "mg2": MinesweeperBuffGame(),  
    "mg3": SolitaireLoveGame(),
}


