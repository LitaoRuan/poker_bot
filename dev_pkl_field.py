"""
Dev tool, not submitted: several submitted pickles against the same field
of dummy and sparring bots, on the same decks, in the arena's format (each
pickle in its own worker, fresh per seat rotation). The fairest way to
compare two finished bots: the tournament ranks by the average over the
field.

    .venv/bin/python dev_pkl_field.py A.pkl B.pkl [--deals N] [--seeds S]
"""

import math
import multiprocessing
import sys
import time

from arena.remote import RemoteModel
from dev_tourney import ALL, _deck
from engine import play_hand


def _match(args):
    pkl, opponent, deals, seed = args
    per_deal = [0.0] * deals
    faults = 0
    for k in (0, 1):
        us = RemoteModel(pkl, timeout=10.0)
        try:
            them = ALL[opponent](seed=seed + k)
            seats = [us, them] if k == 0 else [them, us]
            names = ["us", opponent] if k == 0 else [opponent, "us"]
            for d in range(deals):
                result = play_hand(seats, _deck(f"{seed}:{d}"), [500, 500], 0,
                                   10, 20, names)
                per_deal[d] += result.net[k] / 2 / 20
                faults += k in result.faults
        finally:
            us.close()
    return pkl, opponent, seed, per_deal, faults


def main():
    args = sys.argv[1:]
    opts = {"--deals": "300", "--seeds": "2"}
    for key in list(opts):
        if key in args:
            i = args.index(key)
            opts[key] = args[i + 1]
            del args[i:i + 2]
    pkls = [a for a in args if a.endswith(".pkl")]
    opponents = [a for a in args if not a.endswith(".pkl")] or list(ALL)
    deals, seeds = int(opts["--deals"]), int(opts["--seeds"])
    jobs = [(p, o, deals, 101 + 1000 * s) for o in opponents
            for s in range(seeds) for p in pkls]
    start = time.time()
    got, faults = {}, {p: 0 for p in pkls}
    with multiprocessing.Pool(10) as pool:
        for pkl, opp, seed, per_deal, f in pool.imap_unordered(_match, jobs):
            got[(pkl, opp, seed)] = per_deal
            faults[pkl] += f
    names = [p.rsplit("/", 1)[-1] for p in pkls]
    print(f"{'opponent':12s}" + "".join(f"{n:>16s}" for n in names)
          + "   diff A-B (95%)")
    diffs_all = []
    totals = [0.0] * len(pkls)
    for opp in opponents:
        vals = []
        for p in pkls:
            v = []
            for s in range(seeds):
                v += got[(p, opp, 101 + 1000 * s)]
            vals.append(v)
        means = [100 * sum(v) / len(v) for v in vals]
        for i, m in enumerate(means):
            totals[i] += m
        line = f"{opp:12s}" + "".join(f"{m:+16.1f}" for m in means)
        if len(pkls) == 2:
            d = [a - b for a, b in zip(vals[0], vals[1])]
            mean = sum(d) / len(d)
            se = math.sqrt(sum((x - mean) ** 2 for x in d)
                           / max(1, len(d) - 1) / len(d))
            diffs_all.append((100 * mean, 100 * se))
            line += f"   {100 * mean:+7.1f} +-{196 * se:5.1f}"
        print(line)
    k = len(opponents)
    line = f"{'AVERAGE':12s}" + "".join(f"{t / k:+16.1f}" for t in totals)
    if diffs_all:
        avg = sum(d for d, _ in diffs_all) / k
        se = math.sqrt(sum(s * s for _, s in diffs_all)) / k
        line += f"   {avg:+7.1f} +-{1.96 * se:5.1f}"
    print(line)
    print(f"faults: {faults}   ({time.time() - start:.0f}s)")


if __name__ == "__main__":
    main()
