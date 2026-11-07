# Our bot: an exploitative equity engine

Heads-up no-limit hold'em, 25 big blinds deep. Every decision is the action
with the most expected chips against a model of *this* opponent, learned
during the match. Pure Python (no numpy), well under 0.2 s per move.

## Submitted files

| File | What it does |
|---|---|
| `model.py` | The bot: opponent model, range tracking, decisions, safety layer |
| `handeval.py` | Fast 5–7 card evaluator (lookup tables, ~0.3 µs a hand) and per-street equity |
| `preflop_tables.py` | Generated: 169 × 169 preflop equity matrix and hand ranking |
| `<team>.pkl` | `python -m submit --team <team>` writes it |

Files named `dev_*.py` are our tools and are not submitted.

## How it decides

1. **Range tracking.** A weight for each of the opponent's 1326 possible
   hands. After every action, weights move toward the hands that act that
   way. If a bot bets 30% of the time in a spot, its bets come mostly from
   its strongest 30%. A small "bluff" share stays in, and showdowns
   calibrate it.
2. **Opponent profile.** Counts of fold, call and raise in each spot, each
   with a prior worth 3–4 observations:
   - opening as small blind; facing our limp, our raise, our all-in
   - re-shoves after they raise
   - postflop: first to act, facing our bet (by bet size), facing our raise
     after they bet, facing our all-in
3. **Equity.** Exact on the river and turn, about 160 sampled runouts on
   the flop. Preflop uses the precomputed 169 × 169 table.
4. **Expected value.** It compares fold, check/call, bets of ⅓, ⅔ and a
   full pot, and all-in. A bet's value is
   `P(fold)·pot + P(call)·(equity vs the hands that call·new pot − cost)
   + P(raise)·(the better of folding, or calling off against their raising
   hands)`.
   When more betting is to come, that equity is scaled down for weak hands
   and up for strong ones, and up when acting last.
   - Exploitation comes from the numbers. No bluffs into calling stations,
     who also get big value bets. Constant stealing from folders. Wide calls
     against maniacs. Respect for bots that only bet strong hands.
5. **Safety.**
   - Every move is checked with `validate_action`.
   - Any exception falls back to check-or-fold.
   - The flop has a time budget (0.35 s).
   - Multiway pots (validity tests only) use a simple equity rule.

## Results (local, arena format: 300–400 deals × 2 seats per pairing)

Against all 18 practice bots: ahead of every one. That includes the
repo's dummies (fold, call, random, shove, tight, equity) and our own
sparring bots in `dev_sparring.py`: README example, tight-aggressive,
loose-aggressive, all-in-or-fold, smarter equity, min-raiser, calling
station, slow-player, fit-or-fold, overbettor, check-raiser and
preflop trapper. Typical results: +50 to +190 bb/100 against the
sensible ones, +330 to +420 against the weak ones. The organisers'
validity tests pass (`pytest tests/test_model.py`), and `python -m
submit` reports nothing for the code review to flag.

Tuning (`dev_ab.py`: paired A/B on the same decks): counting the opponent's
re-raise in a bet's value was kept. Nine other changes were within noise or
worse, so they were dropped: bigger opens, more bet sizes, softer ranges,
less mixing, more flop runouts, faster-adapting priors, a bigger post-flop
bonus, tighter re-shoves and per-street bet rates.

## Commands

```sh
.venv/bin/python -m pytest tests/test_model.py -q    # valid submission?
.venv/bin/python -m evals --deals 1000               # vs the dummies
.venv/bin/python dev_tourney.py 300 --seeds 2        # vs every sparring bot
.venv/bin/python dev_strategy.py                     # default preflop play
.venv/bin/python dev_ab.py <module> --seeds 6        # A/B vs dev_model_baseline
.venv/bin/python -m submit --team <team>             # make <team>.pkl
```
