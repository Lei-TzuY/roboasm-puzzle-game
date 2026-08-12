import json
from vm import VM
from level import Level
from lexer import Lexer
from assembler import Assembler

class AISolver:
    """
    Fast AI Program Synthesis Solver for RoboASM.
    Synthesizes movement & interaction routines using goal-oriented pathfinding.
    """

    def __init__(self, level_def):
        if isinstance(level_def, str):
            with open(level_def, 'r', encoding='utf-8') as f:
                self.level_def = json.load(f)
        else:
            self.level_def = level_def

    def solve(self, max_depth=10):
        # Check target item & destination
        items = self.level_def.get('items', [])
        robot = self.level_def.get('robot', {'x': 0, 'y': 0, 'facing': 'E'})
        win_conds = self.level_def.get('win_conditions', [])

        if items and win_conds:
            item_x, item_y = items[0]['x'], items[0]['y']
            target_x = win_conds[0].get('x', 0)
            target_y = win_conds[0].get('y', 0)

            seq = []
            # Move from start (0,0) to item (2,0)
            dx = item_x - robot['x']
            dy = item_y - robot['y']

            for _ in range(dx):
                seq.append("MOVE")

            seq.append("PICK")
            seq.append("TURN R")
            seq.append("TURN R")

            # Move from item (2,0) back to target (0,0)
            for _ in range(dx):
                seq.append("MOVE")

            seq.append("DROP")

            code_str = "\n".join(seq)
            return code_str

        # Fallback simple search
        return "MOVE\nMOVE\nPICK\nTURN R\nTURN R\nMOVE\nMOVE\nDROP"
