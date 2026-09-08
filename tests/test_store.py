"""Database behaviour: migration, dedupe, and per-league season totals."""

import sqlite3

import pytest
import store


def make_game(event_id, league, season, units, result='cover'):
    team = {'display_name': 'Team', 'abbreviation': 'TM'}

    return {
        'event_id': event_id, 'league': league, 'season': season,
        'short_name': 'A @ B', 'start_time': f'{season}-09-05T19:30Z',
        'favorite': team, 'underdog': team, 'spread': -3.5, 'price': -110,
        'favorite_score': 27, 'underdog_score': 20, 'result': result,
        'units': units,
    }


def test_season_totals_are_scoped_by_league_and_season(connection):
    store.record(connection, make_game('1', 'nfl', 2026, 0.91), 'a', True)
    store.record(connection, make_game('2', 'nfl', 2026, -1.0, 'no_cover'),
                 'b', True)
    store.record(connection, make_game('3', 'cfb', 2026, 0.5), 'c', True)
    store.record(connection, make_game('4', 'nfl', 2025, 99.0), 'd', True)

    nfl = store.season_totals(connection, 'nfl', 2026)
    cfb = store.season_totals(connection, 'cfb', 2026)

    assert nfl['games'] == 2
    assert nfl['units'] == pytest.approx(-0.09)
    assert cfb['games'] == 1
    assert cfb['units'] == pytest.approx(0.5)


def test_season_totals_empty_is_zero_not_none(connection):
    totals = store.season_totals(connection, 'nfl', 2026)

    assert totals == {'games': 0, 'covers': 0, 'pushes': 0, 'units': 0.0}


def test_record_is_idempotent(connection):
    game = make_game('1', 'nfl', 2026, 0.91)

    store.record(connection, game, 'text', True)
    store.record(connection, game, 'text', True)

    assert connection.execute(
        'SELECT COUNT(*) FROM posted').fetchone()[0] == 1


def test_is_empty(connection):
    assert store.is_empty(connection)

    store.record(connection, make_game('1', 'nfl', 2026, 0.91), 'x', True)

    assert not store.is_empty(connection)


def test_migration_adds_season_to_a_legacy_database(tmp_path):
    """A database created before the season column must open cleanly."""

    path = tmp_path / 'legacy.db'
    legacy = sqlite3.connect(path)
    legacy.execute(
        """
        CREATE TABLE posted (
            event_id TEXT PRIMARY KEY, league TEXT NOT NULL, short_name TEXT,
            start_time TEXT, favorite TEXT, underdog TEXT, spread REAL,
            price REAL, favorite_score INTEGER, underdog_score INTEGER,
            result TEXT, units REAL, tweet_text TEXT,
            dry_run INTEGER NOT NULL DEFAULT 1,
            posted_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
        """)
    legacy.execute(
        "INSERT INTO posted (event_id, league, units, result) "
        "VALUES ('old', 'nfl', 0.91, 'cover')")
    legacy.commit()
    legacy.close()

    connection = store.connect(str(path))

    columns = {row['name'] for row in
               connection.execute('PRAGMA table_info(posted)')}
    assert 'season' in columns
    assert connection.execute(
        'SELECT COUNT(*) FROM posted').fetchone()[0] == 1
    assert store.already_posted(connection, 'old')
