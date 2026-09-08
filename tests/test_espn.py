"""Parsing of recorded ESPN payloads."""

import espn


def test_parse_event_extracts_final_score(scoreboard):
    events = [espn.parse_event(e) for e in scoreboard['events']]
    events = [e for e in events if e]

    by_name = {e['short_name']: e for e in events}

    lsu = by_name['CLEM @ LSU']
    assert lsu['home']['abbreviation'] == 'LSU'
    assert lsu['away']['abbreviation'] == 'CLEM'
    assert lsu['home_score'] == 51
    assert lsu['away_score'] == 10


def test_parse_event_skips_unfinished_games(scoreboard):
    event = scoreboard['events'][0]
    event['status']['type']['completed'] = False

    assert espn.parse_event(event) is None


def test_parse_event_skips_missing_score(scoreboard):
    event = scoreboard['events'][0]
    for competitor in event['competitions'][0]['competitors']:
        competitor['score'] = None

    assert espn.parse_event(event) is None


def test_odds_uses_explicit_favorite_flag(odds_for):
    parsed = espn._parse_odds_item(odds_for('401856660')['items'][0])

    assert parsed['favorite'] == 'home'
    assert parsed['home_spread'] == -10.0
    assert parsed['source'] == 'close'


def test_odds_prefers_close_over_current(odds_for):
    item = odds_for('401856660')['items'][0]
    item['homeTeamOdds']['close']['pointSpread']['american'] = '-7.5'
    item['homeTeamOdds']['current']['pointSpread']['american'] = '-99.5'

    assert espn._parse_odds_item(item)['home_spread'] == -7.5


def test_odds_falls_back_to_current_before_kickoff(odds_for):
    item = odds_for('401856660')['items'][0]
    del item['homeTeamOdds']['close']

    parsed = espn._parse_odds_item(item)

    assert parsed['source'] == 'current'


def test_american_parses_signed_strings():
    assert espn._american({'american': '+3.5'}) == 3.5
    assert espn._american({'american': '-120'}) == -120.0
    assert espn._american({'american': 'EVEN'}) is None
    assert espn._american({}) is None
