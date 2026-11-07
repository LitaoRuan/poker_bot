"""
Dev tool, not submitted: a paired A/B test of two model files.

    .venv/bin/python dev_ab.py CANDIDATE [--base MODULE] [--deals N]
                               [--seeds S] [opponent ...]

CANDIDATE and the base (default dev_model_baseline) are module names with
a Model class. Both play the same duplicate matches (same decks, same
opponent seeds, arena format) against every opponent; the report gives
each one's bb/100 and the difference with a 95% interval, per opponent
and averaged over opponents, which is how the tournament ranks.
"""

import hashlib
import importlib
import json
import math
import os
import multiprocessing
import pickle
import sys
import time

from dev_tourney import ALL, _deck, _factory
from engine import play_hand


def _match(args):
    module, opponent, deals, seed = args
    blob = pickle.dumps(importlib.import_module(module).Model())
    make = _factory(opponent)
    per_deal = [0.0] * deals
    faults = 0
    for k in (0, 1):
        us = pickle.loads(blob)
        them = make(seed + k)
        seats = [us, them] if k == 0 else [them, us]
        names = ["us", opponent] if k == 0 else [opponent, "us"]
        mine = k
        for d in range(deals):
            result = play_hand(seats, _deck(f"{seed}:{d}"), [500, 500], 0,
                               10, 20, names)
            per_deal[d] += result.net[mine] / 2 / 20
            faults += mine in result.faults
    return module, opponent, seed, per_deal, faults


CACHE = ".ab_cache.json"


def _key(module, opponent, deals, seed):
    with open(module + ".py", "rb") as file:
        digest = hashlib.md5(file.read()).hexdigest()[:12]
    return f"{digest}:{opponent}:{deals}:{seed}"


def report(cand, base, opponents, seeds, got):
    rows = []
    for opp in opponents:
        diffs, a_all, b_all = [], [], []
        for s in range(seeds):
            seed = 101 + 1000 * s
            a, b = got[(cand, opp, seed)], got[(base, opp, seed)]
            diffs += [x - y for x, y in zip(a, b)]
            a_all += a
            b_all += b
        n = len(diffs)
        mean = sum(diffs) / n
        var = sum((x - mean) ** 2 for x in diffs) / max(1, n - 1)
        rows.append((opp, 100 * sum(a_all) / n, 100 * sum(b_all) / n,
                     100 * mean, 100 * math.sqrt(var / n)))
    print(f"{'opponent':12s} {cand:>14s} {base:>14s}   diff (95%)")
    for opp, a, b, d, se in rows:
        print(f"{opp:12s} {a:+14.1f} {b:+14.1f}   {d:+7.1f} +-{1.96 * se:5.1f}")
    k = len(rows)
    avg = sum(r[3] for r in rows) / k
    se = math.sqrt(sum(r[4] ** 2 for r in rows)) / k
    print(f"{'AVERAGE':12s} {sum(r[1] for r in rows) / k:+14.1f} "
          f"{sum(r[2] for r in rows) / k:+14.1f}   {avg:+7.1f} "
          f"+-{1.96 * se:5.1f}")


def main():
    args = sys.argv[1:]
    opts = {"--base": "dev_model_baseline", "--deals": "300", "--seeds": "3"}
    for key in list(opts):
        if key in args:
            i = args.index(key)
            opts[key] = args[i + 1]
            del args[i:i + 2]
    cands = args.pop(0).split(",")
    base = opts["--base"]
    deals, seeds = int(opts["--deals"]), int(opts["--seeds"])
    opponents = args or list(ALL)
    jobs = [(m, o, deals, 101 + 1000 * s) for o in opponents
            for s in range(seeds) for m in cands + [base]]
    start = time.time()
    cache = {}
    if os.path.exists(CACHE):
        with open(CACHE) as file:
            cache = json.load(file)
    got = {}
    faults = {m: 0 for m in cands + [base]}
    todo = []
    for job in jobs:
        hit = cache.get(_key(*job))
        if hit is None:
            todo.append(job)
        else:
            got[(job[0], job[1], job[3])] = hit
    with multiprocessing.Pool(10) as pool:
        for module, opp, seed, per_deal, f in pool.imap_unordered(_match,
                                                                  todo):
            got[(module, opp, seed)] = per_deal
            faults[module] += f
            if f == 0:
                cache[_key(module, opp, deals, seed)] = per_deal
    with open(CACHE, "w") as file:
        json.dump(cache, file)
    for cand in cands:
        report(cand, base, opponents, seeds, got)
    print(f"faults: {faults}   ({time.time() - start:.0f}s)")


if __name__ == "__main__":
    main()
