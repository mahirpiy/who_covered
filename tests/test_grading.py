"""Grading rules: cover, push, and the unit math behind each."""

import pytest

from grading import COVER, NO_COVER, PUSH, evaluate, hashtag, payout


@pytest.mark.parametrize('price, expected', [
    (-110, 0.909091),
    (-120, 0.833333),
    (100, 1.0),
    (150, 1.5),
    (None, 0.909091),  # missing price falls back to standard juice
])
def test_payout(price, expected):
    assert payout(price) == pytest.approx(expected, abs=1e-6)


@pytest.mark.parametrize('spread, fav, dog, expected', [
    (-3.5, 24, 20, COVER),      # wins by 4, needed 3.5
    (-3.5, 24, 21, NO_COVER),   # wins by 3, needed 3.5
    (-3.0, 24, 21, PUSH),       # wins by exactly 3
    (-3.0, 21, 24, NO_COVER),   # loses outright
    (-10.0, 51, 10, COVER),
    (0, 24, 21, COVER),         # pick'em, favorite wins
    (0, 21, 21, PUSH),          # pick'em, tie
])
def test_evaluate_result(spread, fav, dog, expected):
    result, _ = evaluate(spread, fav, dog, -110)
    assert result == expected


def test_push_is_flat_not_a_loss():
    """A push must return zero units, never the loss branch."""

    result, units = evaluate(-3.0, 27, 24, -110)

    assert result == PUSH
    assert units == 0.0


def test_loss_is_exactly_one_unit():
    _, units = evaluate(-7.0, 20, 20, -110)

    assert units == -1.0


def test_win_pays_the_price_not_a_flat_unit():
    _, units = evaluate(-7.0, 30, 20, -110)

    assert units == pytest.approx(0.909091, abs=1e-6)


def test_win_at_plus_money():
    _, units = evaluate(-7.0, 30, 20, 120)

    assert units == pytest.approx(1.2)


@pytest.mark.parametrize('team, league, expected', [
    ({'mascot': '49ers', 'location': 'San Francisco'}, 'nfl', '#49ers'),
    ({'mascot': 'Aggies', 'location': 'Texas A&M'}, 'cfb', '#TexasAM'),
    ({'mascot': 'Bulldogs', 'location': 'Georgia'}, 'cfb', '#Georgia'),
    ({'mascot': '', 'location': '', 'display_name': ''}, 'cfb', ''),
])
def test_hashtag(team, league, expected):
    assert hashtag(team, league) == expected
