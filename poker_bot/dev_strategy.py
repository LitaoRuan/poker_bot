"""
Dev tool, not submitted: the model's preflop play with no data on the
opponent (small blind first in; big blind against a 2bb open).

    .venv/bin/python dev_strategy.py [module]
"""

import importlib
import sys
from collections import Counter

from card_utils import Card
from game_state import GameState, GameStateView
from handeval import RANKS, SUITS, class_name
from player_action import PlayerAction


def card(c):
    return Card(RANKS[c >> 2], SUITS[c & 3])


def main():
    module = sys.argv[1] if len(sys.argv) > 1 else "model"
    m = importlib.import_module(module).Model()
    res = {"sb": {}, "bb": {}}
    for cls in range(169):
        row, col = divmod(cls, 13)
        if row == col:
            a, b = row * 4, row * 4 + 1
        elif row > col:
            a, b = row * 4, col * 4
        else:
            a, b = col * 4, row * 4 + 1
        for seat in ("sb", "bb"):
            acts = Counter()
            for _ in range(5):
                st = GameState([500, 500])
                teams = ["us", "them"] if seat == "sb" else ["them", "us"]
                st.setup_hand([500, 500], 0, 10, 20, teams)
                seen = []
                if seat == "bb":
                    op = PlayerAction.raise_to(0, 40)
                    st.process_action(op)
                    seen = [op]
                m.seed([card(a), card(b)], 0 if seat == "sb" else 1)
                act = m.run(seen, GameStateView(st))
                name = act.kind
                if name == "raise":
                    name = "shove" if act.amount >= 500 else f"raise{act.amount}"
                acts[name] += 1
            res[seat][class_name(cls)] = acts.most_common(1)[0][0]
    for seat in ("sb", "bb"):
        counts = Counter(res[seat].values())
        print(seat.upper(), dict(counts))
        for kind in sorted(counts):
            if kind.startswith("raise") and seat == "sb":
                continue
            if kind == "call" and seat == "bb":
                continue
            hands = sorted(k for k, v in res[seat].items() if v == kind)
            print(f"  {kind}: {' '.join(hands)}")


if __name__ == "__main__":
    main()
