"""SQLite record of games already posted, so a restart never double-tweets."""

import logging
import os
import sqlite3

LOG = logging.getLogger(__name__)

DEFAULT_DB_PATH = os.environ.get('CHALK_REPORT_DB', 'data/chalk_report.db')

SCHEMA = """
CREATE TABLE IF NOT EXISTS posted (
    event_id      TEXT PRIMARY KEY,
    league        TEXT NOT NULL,
    season        INTEGER,
    short_name    TEXT,
    start_time    TEXT,
    favorite      TEXT,
    underdog      TEXT,
    spread        REAL,
    price         REAL,
    favorite_score INTEGER,
    underdog_score INTEGER,
    result        TEXT,
    units         REAL,
    tweet_text    TEXT,
    dry_run       INTEGER NOT NULL DEFAULT 1,
    posted_at     TEXT NOT NULL DEFAULT (datetime('now'))
);

"""

# Indexes are applied after the migration below, since some of them reference
# columns that an older database file will not have yet.
INDEXES = """
CREATE INDEX IF NOT EXISTS posted_league_start ON posted (league, start_time);
CREATE INDEX IF NOT EXISTS posted_league_season ON posted (league, season);
"""

# Columns added after the first release, applied on open so existing databases
# pick them up without a manual migration step.
ADDED_COLUMNS = (
    ('season', 'INTEGER'),
)


def connect(db_path=None):
    """Opens the database, creating the file and schema if needed."""

    db_path = db_path or DEFAULT_DB_PATH

    directory = os.path.dirname(os.path.abspath(db_path))
    os.makedirs(directory, exist_ok=True)

    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    connection.executescript(SCHEMA)
    _migrate(connection)
    connection.executescript(INDEXES)
    connection.commit()

    LOG.info('using database %s', db_path)

    return connection


def _migrate(connection):
    """Adds any columns missing from an older database file."""

    existing = {row['name'] for row in
                connection.execute('PRAGMA table_info(posted)')}

    for name, column_type in ADDED_COLUMNS:
        if name not in existing:
            LOG.info('adding column %s to posted', name)
            connection.execute(
                f'ALTER TABLE posted ADD COLUMN {name} {column_type}')


def already_posted(connection, event_id):
    """True when this event has already produced a tweet."""

    row = connection.execute(
        'SELECT 1 FROM posted WHERE event_id = ?', (event_id,)).fetchone()

    return row is not None


def is_empty(connection):
    """True when no game has ever been recorded.

    Used to refuse a first --live run against a fresh database, which would
    otherwise tweet every game already final in the polling window.
    """

    row = connection.execute('SELECT 1 FROM posted LIMIT 1').fetchone()

    return row is None


def record(connection, game, tweet_text, dry_run):
    """Marks an event as posted.

    Uses INSERT OR IGNORE so a race between two poll cycles cannot produce a
    second row -- the caller checks already_posted first, but this is the
    guarantee that actually holds.
    """

    connection.execute(
        """
        INSERT OR IGNORE INTO posted (
            event_id, league, season, short_name, start_time, favorite,
            underdog, spread, price, favorite_score, underdog_score, result,
            units, tweet_text, dry_run
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            game['event_id'], game['league'], game['season'],
            game['short_name'],
            game['start_time'], game['favorite']['display_name'],
            game['underdog']['display_name'], game['spread'], game['price'],
            game['favorite_score'], game['underdog_score'], game['result'],
            game['units'], tweet_text, 1 if dry_run else 0,
        ),
    )
    connection.commit()


def season_totals(connection, league, season):
    """Running record and units for one league's season.

    This is the season-to-date line printed at the bottom of every tweet, so
    it is deliberately scoped to a single league -- NFL and college numbers
    are tracked separately.
    """

    row = connection.execute(
        """
        SELECT
            COUNT(*) AS games,
            COALESCE(SUM(result = 'cover'), 0) AS covers,
            COALESCE(SUM(result = 'push'), 0) AS pushes,
            COALESCE(SUM(units), 0.0) AS units
        FROM posted
        WHERE league = ? AND season = ?
        """,
        (league, season),
    ).fetchone()

    return dict(row)


def summary(connection, league=None):
    """Aggregate record and units, optionally scoped to one league."""

    where = 'WHERE league = ?' if league else ''
    params = (league,) if league else ()

    row = connection.execute(
        f"""
        SELECT
            COUNT(*) AS games,
            SUM(result = 'cover') AS covers,
            SUM(result = 'push') AS pushes,
            COALESCE(SUM(units), 0) AS units
        FROM posted {where}
        """,
        params,
    ).fetchone()

    return dict(row)
