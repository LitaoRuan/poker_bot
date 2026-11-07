"""
Dev tool, not submitted: sparring bots that play like other teams might.

Each is built as Cls(seed) and has seed/run like a submitted Model.
"""

import random

import preflop_tables
from card_utils import evaluate
from handeval import Evaluator, card_id, hand_class
from player_action import PlayerAction

_EV = Evaluator()


def _pf_strength(hand):
    ids = [card_id(c) for c in hand]
    return preflop_tables.HS[hand_class(ids[0], ids[1])] / 10000.0


def _equity(hand, board, rng, samples=200):
    return _EV.equity_multi([card_id(c) for c in hand],
                            [card_id(c) for c in board], 1, rng, samples)


class _Base:
    def __init__(self, seed=None):
        self.hand = []
        self.player_id = None
        self.rng = random.Random(seed)

    def seed(self, hand, player_id):
        self.hand = hand
        self.player_id = player_id

    def _call(self):
        return PlayerAction.call(self.player_id)

    def _fold_or_check(self, gs):
        if gs.call_amount == 0:
            return PlayerAction.call(self.player_id)
        return PlayerAction.fold(self.player_id)

    def _raise(self, gs, total):
        if not gs.can_raise:
            return self._call()
        low, high = gs.raise_range
        return PlayerAction.raise_to(self.player_id,
                                     int(min(high, max(low, total))))


class ExampleBot(_Base):
    """The README's example bot, which many teams start from."""

    def run(self, actions, gs):
        if len(gs.board) >= 3:
            strong = evaluate(self.hand + list(gs.board))[0] >= 2
        else:
            high, low = sorted(card.value for card in self.hand)[::-1]
            strong = high == low or low >= 10
        if strong and "raise" in gs.legal_actions:
            low, high = gs.raise_range
            return PlayerAction.raise_to(self.player_id,
                                         min(high, max(low, gs.pot)))
        if gs.call_amount == 0 or gs.pot_odds < 0.25:
            return self._call()
        return PlayerAction.fold(self.player_id)


class TagBot(_Base):
    """Tight-aggressive: raises good hands 2.5x, 3-bets premiums, bets
    2/3 pot with equity, c-bets some air, folds to aggression without it."""

    def run(self, actions, gs):
        if gs.street == "preflop":
            s = _pf_strength(self.hand)
            if gs.call_amount <= gs.big_blind / 2:  # unopened or limped
                if s > 0.56:
                    return self._raise(gs, 2.5 * gs.big_blind)
                if gs.call_amount == 0:
                    return self._call()
                return self._call() if s > 0.48 else self._fold_or_check(gs)
            if s > 0.66:
                return self._raise(gs, gs.max_raise_to)
            if s > 0.55 and gs.pot_odds < 0.4:
                return self._call()
            return self._fold_or_check(gs)
        e = _equity(self.hand, gs.board, self.rng)
        if e > 0.75 and gs.can_raise:
            return self._raise(gs, gs.current_bet + gs.pot)
        if gs.call_amount == 0:
            if e > 0.6 or self.rng.random() < 0.25:
                return self._raise(gs, gs.pot * 0.66)
            return self._call()
        if e > gs.pot_odds + 0.1:
            return self._call()
        return PlayerAction.fold(self.player_id)


class LagBot(_Base):
    """Loose-aggressive: raises most hands, bets often, calls wide."""

    def run(self, actions, gs):
        if gs.street == "preflop":
            s = _pf_strength(self.hand)
            if s > 0.62:
                return self._raise(gs, max(3 * gs.current_bet, gs.pot))
            if s > 0.40 and gs.call_amount <= 3 * gs.big_blind:
                if self.rng.random() < 0.6:
                    return self._raise(gs, 3 * gs.big_blind)
                return self._call()
            return self._fold_or_check(gs)
        e = _equity(self.hand, gs.board, self.rng)
        if gs.call_amount == 0:
            if e > 0.5 or self.rng.random() < 0.45:
                return self._raise(gs, gs.pot * (0.5 + e))
            return self._call()
        if e > 0.7:
            return self._raise(gs, gs.current_bet + gs.pot)
        if e > gs.pot_odds - 0.05:
            return self._call()
        return PlayerAction.fold(self.player_id)


class PushFoldBot(_Base):
    """Short-stack chart: shoves or folds preflop, nothing else."""

    def run(self, actions, gs):
        s = _pf_strength(self.hand)
        if gs.street != "preflop":
            e = _equity(self.hand, gs.board, self.rng)
            if e > 0.55:
                return self._raise(gs, gs.max_raise_to)
            return self._fold_or_check(gs)
        if gs.current_bet <= gs.big_blind:
            if gs.call_amount > 0:  # small blind, unopened
                return (self._raise(gs, gs.max_raise_to) if s > 0.45
                        else self._fold_or_check(gs))
            return (self._raise(gs, gs.max_raise_to) if s > 0.55
                    else self._call())
        return self._call() if s > 0.53 else self._fold_or_check(gs)


class SmartEquityBot(_Base):
    """Equity against a random hand, with sizes by strength, pot-odds
    calls and some bluffs: a decent hackathon bot."""

    def run(self, actions, gs):
        if gs.street == "preflop":
            e = _pf_strength(self.hand)
        else:
            e = _equity(self.hand, gs.board, self.rng, 300)
        if gs.call_amount == 0:
            if e > 0.62 and gs.can_raise:
                return self._raise(gs, gs.current_bet + gs.pot * (e - 0.1))
            if e < 0.35 and self.rng.random() < 0.2 and gs.can_raise:
                return self._raise(gs, gs.current_bet + gs.pot * 0.5)
            return self._call()
        if e > 0.8 and gs.can_raise:
            return self._raise(gs, gs.current_bet * 2 + gs.pot)
        if e > gs.pot_odds + 0.05:
            return self._call()
        return PlayerAction.fold(self.player_id)


class MinRaiseBot(_Base):
    """Min-raises with any decent hand, calls the rest."""

    def run(self, actions, gs):
        s = (_pf_strength(self.hand) if gs.street == "preflop"
             else _equity(self.hand, gs.board, self.rng, 100))
        if s > 0.5 and gs.can_raise:
            return self._raise(gs, gs.min_raise_to)
        if s > 0.3 or gs.call_amount == 0:
            return self._call()
        return PlayerAction.fold(self.player_id)


class StationBot(_Base):
    """Calls almost everything, raises only with very strong hands."""

    def run(self, actions, gs):
        s = (_pf_strength(self.hand) if gs.street == "preflop"
             else _equity(self.hand, gs.board, self.rng, 150))
        if s > 0.8 and gs.can_raise:
            return self._raise(gs, gs.current_bet + gs.pot)
        if s > 0.2 or gs.call_amount == 0:
            return self._call()
        return PlayerAction.fold(self.player_id)


class TrapperBot(_Base):
    """Plays strong hands slowly: checks them, then check-raises or
    raises when bet into; folds weak hands to bets."""

    def run(self, actions, gs):
        if gs.street == "preflop":
            s = _pf_strength(self.hand)
            if s > 0.7 and gs.call_amount > gs.big_blind / 2:
                return self._raise(gs, gs.max_raise_to)
            if s > 0.42:
                return self._call()
            return self._fold_or_check(gs)
        e = _equity(self.hand, gs.board, self.rng)
        if gs.call_amount == 0:
            if e > 0.7 and gs.street == "river":
                return self._raise(gs, gs.pot)
            return self._call()
        if e > 0.7:
            return self._raise(gs, gs.current_bet + gs.pot)
        if e > 0.45 and gs.pot_odds < 0.35:
            return self._call()
        return PlayerAction.fold(self.player_id)


class FitFoldBot(_Base):
    """Calls preflop with most hands, then continues only with a pair or
    better (using a hole card) or a big draw; bets its made hands."""

    def run(self, actions, gs):
        if gs.street == "preflop":
            s = _pf_strength(self.hand)
            if s > 0.65:
                return self._raise(gs, 3 * gs.current_bet)
            if s > 0.38 and gs.call_amount <= 4 * gs.big_blind:
                return self._call()
            return self._fold_or_check(gs)
        board = list(gs.board)
        made = evaluate(self.hand + board)[0]
        ranks = {c.rank for c in board}
        uses = (self.hand[0].rank == self.hand[1].rank
                or any(c.rank in ranks for c in self.hand))
        if made >= 2 or (made == 1 and uses):
            if gs.call_amount == 0:
                return self._raise(gs, gs.pot * 0.6)
            return self._call()
        return self._fold_or_check(gs)


SPARRING = {
    "trapper": TrapperBot,
    "fitfold": FitFoldBot,
    "example": ExampleBot,
    "tag": TagBot,
    "lag": LagBot,
    "pushfold": PushFoldBot,
    "smarteq": SmartEquityBot,
    "minraise": MinRaiseBot,
    "station": StationBot,
}
