"""End-to-end behaviour: grading a slate, seeding, dedupe, and safety rails."""

import bot
import espn
import pytest
import store


class FakeShutdown:
    requested = False


def options(**overrides):
    settings = {'dry_run': True, 'seed': False, 'pace': 0,
                'shutdown': FakeShutdown()}
    settings.update(overrides)

    return bot.Options(**settings)


@pytest.fixture
def stub_espn(monkeypatch, scoreboard, odds_for):
    """Serves the recorded payloads instead of hitting the network."""

    monkeypatch.setattr(espn, 'scoreboard', lambda league, date:
                        scoreboard['events'])
    monkeypatch.setattr(bot.espn, 'scoreboard', lambda league, date:
                        scoreboard['events'])
    monkeypatch.setattr(bot.espn, 'game_odds', lambda league, eid, cid=None:
                        espn._parse_odds_item(odds_for(eid)['items'][0]))


# --- season boundaries ---------------------------------------------------

@pytest.mark.parametrize('start_time, expected', [
    ('2026-09-05T19:30Z', 2026),
    ('2026-12-31T18:00Z', 2026),
    ('2027-01-11T18:00Z', 2026),   # playoffs belong to the prior season
    ('2027-02-08T23:30Z', 2026),
    ('2027-08-30T16:00Z', 2027),
])
def test_season_for(start_time, expected):
    assert bot.season_for(start_time) == expected


# --- tweet composition ---------------------------------------------------

def test_tweet_shows_league_scoped_season_total():
    game = {
        'league': 'nfl', 'season': 2026, 'result': 'cover', 'units': 0.91,
        'spread': -3.5, 'favorite_score': 27, 'underdog_score': 20,
        'favorite': {'mascot': 'Eagles', 'location': 'Philadelphia',
                     'abbreviation': 'PHI', 'display_name': 'Eagles'},
        'underdog': {'mascot': 'Cowboys', 'location': 'Dallas',
                     'abbreviation': 'DAL', 'display_name': 'Cowboys'},
    }

    text = bot.build_tweet(game, -4.25)

    assert '📊 NFL favorites 2026: -4.25u' in text
    assert 'CFB' not in text


@pytest.mark.parametrize('spread, expected', [
    (-3.5, '-3.5'), (-10.0, '-10'), (0, 'PK'), (2.5, '+2.5'),
])
def test_format_spread(spread, expected):
    assert bot.format_spread(spread) == expected


def test_away_favorite_flips_the_home_quoted_spread():
    event = {
        'event_id': '1', 'competition_id': '1', 'short_name': 'A @ B',
        'start_time': '2026-09-05T19:30Z',
        'home': {'display_name': 'Home', 'abbreviation': 'HOME',
                 'mascot': 'Bears', 'location': 'Homeville'},
        'away': {'display_name': 'Away', 'abbreviation': 'AWAY',
                 'mascot': 'Lions', 'location': 'Awayville'},
        'home_score': 17, 'away_score': 24,
    }
    odds = {'home_spread': 6.5, 'home_price': -110, 'favorite': 'away',
            'provider': 'p', 'source': 'close'}

    game = bot.build_game('nfl', event, odds)

    assert game['spread'] == -6.5
    assert game['favorite']['abbreviation'] == 'AWAY'
    assert game['result'] == 'cover'


def test_every_tweet_fits(connection, stub_espn):
    bot.process_date(connection, 'cfb', '20260905', options())

    for row in connection.execute('SELECT tweet_text FROM posted'):
        assert len(row['tweet_text']) <= 280


# --- dedupe and seeding --------------------------------------------------

def test_games_are_posted_once(connection, stub_espn):
    first = bot.process_date(connection, 'cfb', '20260905', options())
    second = bot.process_date(connection, 'cfb', '20260905', options())

    assert first > 0
    assert second == 0


def test_seed_records_without_sending(connection, stub_espn, monkeypatch):
    sent = []
    monkeypatch.setattr(bot, 'send_tweet',
                        lambda text, dry_run: sent.append(text))

    handled = bot.process_date(connection, 'cfb', '20260905',
                               options(seed=True))

    assert handled > 0
    assert sent == []
    assert not store.is_empty(connection)


def test_live_against_empty_database_is_refused(tmp_path, monkeypatch):
    monkeypatch.setattr(bot, 'preflight', lambda: None)

    code = bot.main(['--live', '--once', '--db', str(tmp_path / 'fresh.db')])

    assert code == 1


# --- failure isolation ---------------------------------------------------

def test_one_broken_game_does_not_stop_the_slate(connection, stub_espn,
                                                 monkeypatch):
    calls = {'n': 0}
    real = bot.build_game

    def explode(league, event, odds):
        calls['n'] += 1
        if calls['n'] == 1:
            raise KeyError('unexpected ESPN shape')
        return real(league, event, odds)

    monkeypatch.setattr(bot, 'build_game', explode)

    handled = bot.process_date(connection, 'cfb', '20260905', options())

    assert handled >= 1  # the surviving game still posted


def test_scoreboard_failure_returns_zero(connection, monkeypatch):
    def boom(league, date):
        raise espn.EspnError('ESPN down')

    monkeypatch.setattr(bot.espn, 'scoreboard', boom)

    assert bot.process_date(connection, 'cfb', '20260905', options()) == 0


def test_send_failure_leaves_game_unrecorded(connection, stub_espn,
                                             monkeypatch):
    def boom(text, dry_run):
        raise RuntimeError('twitter down')

    monkeypatch.setattr(bot, 'send_tweet', boom)

    handled = bot.process_date(connection, 'cfb', '20260905', options())

    assert handled == 0
    assert store.is_empty(connection)  # retried on the next pass


def test_seed_on_empty_absorbs_the_first_pass(tmp_path, monkeypatch,
                                              scoreboard, odds_for):
    """A blank volume must not dump a whole slate onto the timeline."""

    sent = []
    monkeypatch.setattr(bot, 'preflight', lambda: None)
    monkeypatch.setattr(bot, 'send_tweet',
                        lambda text, dry_run: sent.append(text))
    monkeypatch.setattr(bot.espn, 'scoreboard',
                        lambda league, date: scoreboard['events'])
    monkeypatch.setattr(bot.espn, 'game_odds', lambda league, eid, cid=None:
                        espn._parse_odds_item(odds_for(eid)['items'][0]))

    code = bot.main(['--live', '--seed-on-empty', '--once', '--leagues', 'cfb',
                     '--date', '20260905', '--db', str(tmp_path / 'v.db')])

    assert code == 0
    assert sent == []

    connection = store.connect(str(tmp_path / 'v.db'))
    assert not store.is_empty(connection)


def test_preflight_catches_a_broken_tweepy(monkeypatch):
    """tweepy is imported lazily, so --live must prove it works at startup."""

    import builtins

    import tweet

    real_import = builtins.__import__

    def fail(name, *args, **kwargs):
        if name == 'tweepy':
            raise ImportError("No module named 'imghdr'")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, '__import__', fail)

    with pytest.raises(RuntimeError, match='cannot import tweepy'):
        tweet.preflight()


def test_preflight_reports_missing_credentials(monkeypatch):
    import tweet

    for name in tweet.CREDENTIAL_NAMES:
        monkeypatch.delenv(name, raising=False)

    with pytest.raises(RuntimeError, match='missing Twitter credentials'):
        tweet.preflight()


def test_live_exits_when_preflight_fails(tmp_path, monkeypatch):
    monkeypatch.setattr(bot, 'preflight',
                        lambda: (_ for _ in ()).throw(RuntimeError('nope')))

    assert bot.main(['--live', '--once', '--db', str(tmp_path / 'p.db')]) == 1


def test_limit_stops_after_n_games(connection, stub_espn):
    opts = options(limit=1)

    handled = bot.process_date(connection, 'cfb', '20260905', opts)

    assert handled == 1
    assert connection.execute(
        'SELECT COUNT(*) FROM posted').fetchone()[0] == 1


def test_limit_applies_across_dates_and_leagues(connection, stub_espn):
    opts = options(limit=1)

    bot.run_once(connection, ['cfb'], ['20260905', '20260906'], opts)

    assert opts.posted == 1


def test_no_limit_posts_everything(connection, stub_espn):
    opts = options()

    handled = bot.process_date(connection, 'cfb', '20260905', opts)

    assert handled > 1
    assert opts.limit is None


def test_games_post_in_kickoff_order(connection, stub_espn):
    """Backfills must accumulate season totals in the order games were played."""

    bot.process_date(connection, 'cfb', '20260905', options())

    times = [row['start_time'] for row in connection.execute(
        'SELECT start_time FROM posted ORDER BY posted_at, rowid')]

    assert times == sorted(times)
