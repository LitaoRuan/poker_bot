"""
Dev tool, not submitted: our model against sparring and dummy bots, in
the arena's format (duplicate deals, two seat rotations, the button
fixed on seat 0, a fresh model from the pickle per rotation, 500 chips,
10/20 blinds), one pairing per process.

    .venv/bin/python dev_tourney.py [deals] [opponent ...] [--model mod:Cls]

Prints bb/100 for our model in each pairing, with a rough 95% interval,
and any faults or slow moves.
"""

import importlib
import math
import multiprocessing
import pickle
import random
import sys
import time

from arena.dummies import DUMMIES
from card_utils import full_deck
from dev_sparring import SPARRING
from engine import play_hand

ALL = {**DUMMIES, **SPARRING}


def _deck(key):
    deck = full_deck()
    random.Random(key).shuffle(deck)
    return deck


def _factory(spec):
    """A dummy or sparring name, or mod:module:Class for a model file."""
    if spec.startswith("mod:"):
        module, _, cls = spec[4:].partition(":")
        blob = pickle.dumps(getattr(importlib.import_module(module),
                                    cls or "Model")())
        return lambda seed: pickle.loads(blob)
    return ALL[spec]


def _pairing(args):
    model_spec, opponent, deals, seed = args
    module, _, cls = model_spec.partition(":")
    blob = pickle.dumps(getattr(importlib.import_module(module), cls)())
    make = _factory(opponent)
    per_deal = [0.0] * deals
    faults = 0
    slowest = 0.0
    start = time.time()
    for k in (0, 1):
        us = pickle.loads(blob)
        them = make(seed + k)
        seats = [us, them] if k == 0 else [them, us]
        names = ["us", opponent] if k == 0 else [opponent, "us"]
        mine = 0 if k == 0 else 1
        for d in range(deals):
            result = play_hand(seats, _deck(f"{seed}:{d}"), [500, 500], 0,
                               10, 20, names)
            per_deal[d] += result.net[mine] / 2 / 20
            if mine in result.faults:
                faults += 1
                if faults <= 3:
                    print("FAULT", opponent, result.faults[mine],
                          flush=True)
        slowest = max(slowest, getattr(us, "slowest", 0.0))
    mean = sum(per_deal) / deals
    var = sum((x - mean) ** 2 for x in per_deal) / max(1, deals - 1)
    half = 1.96 * math.sqrt(var / deals)
    return opponent, 100 * mean, 100 * half, faults, slowest, \
        time.time() - start


def main():
    args = sys.argv[1:]
    model = "model:Model"
    seeds = 1
    if "--model" in args:
        i = args.index("--model")
        model = args[i + 1]
        del args[i:i + 2]
    if "--seeds" in args:
        i = args.index("--seeds")
        seeds = int(args[i + 1])
        del args[i:i + 2]
    deals = int(args[0]) if args and args[0].isdigit() else 300
    names = [a for a in args if not a.isdigit()] or list(ALL)
    jobs = [(model, name, deals, 17 + 1000 * j)
            for name in names for j in range(seeds)]
    results = {name: [] for name in names}
    with multiprocessing.Pool(min(len(jobs), 10)) as pool:
        for name, bb, half, faults, slowest, secs in pool.imap_unordered(
                _pairing, jobs):
            results[name].append(bb)
            print(f"{name:22s} {bb:+8.1f} bb/100  +-{half:5.1f}  "
                  f"faults {faults}  slowest {slowest:.3f}s  "
                  f"({secs:.0f}s)", flush=True)
    means = {name: sum(v) / len(v) for name, v in results.items()}
    if seeds > 1:
        for name in names:
            print(f"  {name:22s} mean {means[name]:+8.1f}")
    print(f"average over {len(names)}: "
          f"{sum(means.values()) / len(names):+.1f} bb/100")


if __name__ == "__main__":
    main()
