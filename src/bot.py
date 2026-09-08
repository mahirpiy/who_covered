"""Polls ESPN for finished football games and posts one tweet per game.

Each completed game is graded against its closing spread and tweeted once.
SQLite holds the set of games already posted, so the poller is safe to
restart and safe to run on a cron.

Defaults to print-only; pass --live to actually post.
"""

import argparse
import logging
import signal
import sys
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import espn
import store
from tweet import preflight, send_tweet
from grading import COVER, NO_COVER, PUSH, evaluate, hashtag

LOG = logging.getLogger('chalk_report')

# ESPN buckets its slates by US Eastern date.
EASTERN = ZoneInfo('America/New_York')

LEAGUE_LABEL = {
    'nfl': '🏈 NFL',
    'cfb': '🏈 CFB',
}

LEAGUE_NAME = {
    'nfl': 'NFL',
    'cfb': 'CFB',
}

RESULT_MARK = {
    COVER: '✅',
    NO_COVER: '❌',
    PUSH: '🤝',
}

RESULT_PHRASE = {
    COVER: 'covered',
    NO_COVER: 'did not cover',
    PUSH: 'pushed',
}


class Shutdown:
    """Flips on SIGTERM/SIGINT so the loop can finish cleanly.

    Railway sends SIGTERM on every redeploy. Without this the process can be
    killed between sending a tweet and recording it, which would re-post that
    game on the next boot.
    """

    def __init__(self):
        self.requested = False

    def install(self):
        for received in (signal.SIGTERM, signal.SIGINT):
            signal.signal(received, self._handle)

        return self

    def _handle(self, signum, _frame):
        LOG.info('received signal %s, finishing current game then exiting',
                 signum)
        self.requested = True


def eastern_dates():
    """Today and yesterday in Eastern, as ESPN's YYYYMMDD date strings.

    Yesterday is included because late kickoffs finish after midnight Eastern
    while still belonging to the previous day's slate.
    """

    now = datetime.now(EASTERN)

    return [(now - timedelta(days=offset)).strftime('%Y%m%d') for offset in (1, 0)]


def season_for(start_time):
    """Returns the football season a kickoff belongs to.

    A season spans August through February, so January and February games
    belong to the previous calendar year's season.
    """

    try:
        year = int(start_time[:4])
        month = int(start_time[5:7])
    except (TypeError, ValueError):
        return datetime.now(EASTERN).year

    return year if month >= 8 else year - 1


def build_game(league, event, odds):
    """Combines a parsed event and its odds into a graded game."""

    if odds['favorite'] == 'home':
        favorite, underdog = event['home'], event['away']
        favorite_score, underdog_score = event['home_score'], event['away_score']
        spread = odds['home_spread']
    else:
        favorite, underdog = event['away'], event['home']
        favorite_score, underdog_score = event['away_score'], event['home_score']
        # ESPN quotes the spread from the home side, so flip it for the away
        # favorite. The price is the home price and is close enough to the
        # away price for unit math at standard juice.
        spread = -odds['home_spread']

    result, units = evaluate(
        favorite_spread=spread,
        favorite_score=favorite_score,
        underdog_score=underdog_score,
        favorite_price=odds['home_price'],
    )

    return {
        'event_id': event['event_id'],
        'league': league,
        'season': season_for(event['start_time']),
        'short_name': event['short_name'],
        'start_time': event['start_time'],
        'favorite': favorite,
        'underdog': underdog,
        'favorite_score': favorite_score,
        'underdog_score': underdog_score,
        'spread': spread,
        'price': odds['home_price'],
        'result': result,
        'units': units,
        'provider': odds['provider'],
        'line_source': odds['source'],
    }


def format_spread(spread):
    """Renders a spread the way a book would: -3.5, +0, PK."""

    if spread == 0:
        return 'PK'

    trimmed = f'{spread:g}'

    return trimmed if spread < 0 else f'+{trimmed}'


def build_tweet(game, running_units):
    """Composes the single tweet for one finished game.

    ``running_units`` is this league's season-to-date total including the game
    being tweeted. NFL and college totals are tracked separately.
    """

    league = game['league']
    favorite = game['favorite']
    underdog = game['underdog']

    lines = [
        LEAGUE_LABEL[league],
        '',
        f'{RESULT_MARK[game["result"]]} {hashtag(favorite, league)} '
        f'({format_spread(game["spread"])}) {RESULT_PHRASE[game["result"]]} '
        f'vs {hashtag(underdog, league)}',
        '',
        f'Final: {favorite["abbreviation"]} {game["favorite_score"]}, '
        f'{underdog["abbreviation"]} {game["underdog_score"]}',
        f'{game["units"]:+.2f}u',
        '',
        f'📊 {LEAGUE_NAME[league]} favorites {game["season"]}: '
        f'{running_units:+.2f}u',
    ]

    return '\n'.join(lines)


def process_date(connection, league, date, options):
    """Grades and posts every newly completed game on one date.

    Returns the number of games handled. A failure on one game is logged and
    skipped so it cannot take down the rest of the slate or the poll loop.
    """

    try:
        events = espn.scoreboard(league, date)
    except espn.EspnError as error:
        LOG.error('scoreboard %s %s failed: %s', league, date, error)
        return 0

    # Post in kickoff order so "the first game" means the first game, and so a
    # backfill accumulates its season totals in the order the games were
    # actually played.
    events = sorted(events, key=lambda event: event.get('date', ''))

    handled = 0

    for raw_event in events:
        if options.shutdown.requested or options.exhausted():
            break

        try:
            handled += _process_event(connection, league, raw_event, options,
                                      first_of_pass=handled == 0)
        except Exception:  # noqa: BLE001 - one bad game must not stop the rest
            LOG.exception('failed to handle event %s',
                          raw_event.get('id', '?'))

    return handled


def _process_event(connection, league, raw_event, options, first_of_pass):
    """Handles a single scoreboard event. Returns 1 if it was posted."""

    event = espn.parse_event(raw_event)
    if event is None:
        return 0

    if store.already_posted(connection, event['event_id']):
        return 0

    odds = espn.game_odds(league, event['event_id'], event['competition_id'])

    if odds is None:
        # No line means nothing to grade. Left unrecorded so a later pass can
        # retry once ESPN stamps the closing number.
        LOG.info('skipping %s (%s): no spread yet',
                 event['short_name'], event['event_id'])
        return 0

    game = build_game(league, event, odds)

    # The season line includes this game, so add it to the stored total rather
    # than reading back after the insert -- that keeps the write after the
    # send, so a failed tweet is retried next pass.
    prior = store.season_totals(connection, league, game['season'])['units']
    running_units = prior + game['units']

    text = build_tweet(game, running_units)

    if options.seed:
        # Backfill only: record the game as handled without tweeting it, so a
        # first deployment does not dump an entire slate onto the timeline.
        store.record(connection, game, text, dry_run=True)
        LOG.info('seeded %s %s (%s, %+.2fu)', league, game['short_name'],
                 game['result'], game['units'])
        options.posted += 1
        return 1

    # Space out sends so a slate finishing together does not post as a burst.
    if not first_of_pass and not options.dry_run and options.pace > 0:
        time.sleep(options.pace)

    try:
        send_tweet(text, dry_run=options.dry_run)
    except Exception:  # noqa: BLE001 - never lose the loop over one send
        LOG.exception('send failed for %s, will retry next pass',
                      event['short_name'])
        return 0

    store.record(connection, game, text, options.dry_run)
    options.posted += 1

    LOG.info('posted %s %s (%s, %+.2fu, season %+.2fu)', league,
             game['short_name'], game['result'], game['units'], running_units)

    return 1


def run_once(connection, leagues, dates, options):
    """One full pass over every league and date."""

    total = 0

    for date in sorted(dates):
        for league in leagues:
            if options.shutdown.requested or options.exhausted():
                break
            total += process_date(connection, league, date, options)

    return total


class Options:
    """Runtime settings threaded through the pass."""

    def __init__(self, dry_run, seed, pace, shutdown, limit=None):
        self.dry_run = dry_run
        self.seed = seed
        self.pace = pace
        self.shutdown = shutdown
        self.limit = limit
        self.posted = 0

    def exhausted(self):
        """True once this run has posted as many games as it is allowed to."""

        return self.limit is not None and self.posted >= self.limit


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--leagues', nargs='+', default=['nfl', 'cfb'],
                        choices=sorted(espn.LEAGUE_PATH),
                        help='leagues to poll (default: nfl cfb)')
    parser.add_argument('--interval', type=int, default=120,
                        help='seconds between polls (default: 120)')
    parser.add_argument('--once', action='store_true',
                        help='run a single pass and exit')
    parser.add_argument('--date', nargs='+', metavar='YYYYMMDD',
                        help='specific Eastern dates to grade, for backfill')
    parser.add_argument('--live', action='store_true',
                        help='actually post to Twitter (default: print only)')
    parser.add_argument('--seed', action='store_true',
                        help='record games as handled without tweeting; run '
                             'this once before the first --live deploy')
    parser.add_argument('--seed-on-empty', action='store_true',
                        help='with --live, silently seed the first pass when '
                             'the database is empty instead of refusing. Use '
                             'this on a hosted deploy, where the volume may '
                             'start out blank.')
    parser.add_argument('--pace', type=int, default=20,
                        help='seconds between posted tweets (default: 20)')
    parser.add_argument('--limit', type=int, default=None,
                        help='stop after posting this many games. Use '
                             '--limit 1 to verify a live deploy with a single '
                             'tweet before backfilling the rest.')
    parser.add_argument('--db', default=None,
                        help='SQLite path (default: $CHALK_REPORT_DB)')
    parser.add_argument('--verbose', action='store_true')

    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format='%(asctime)s %(levelname)s %(name)s: %(message)s',
    )

    dry_run = not args.live

    if args.seed and args.live:
        parser.error('--seed and --live are mutually exclusive')

    if args.live:
        try:
            preflight()
        except RuntimeError as error:
            LOG.error('%s', error)
            return 1

    shutdown = Shutdown().install()
    connection = store.connect(args.db)

    seed_first_pass = False

    if args.live and not args.seed and store.is_empty(connection):
        if args.seed_on_empty:
            # A blank volume on a fresh deploy would otherwise tweet every
            # game already final in the polling window. Absorb that first pass
            # silently, then post normally from the next one.
            LOG.warning('database is empty; seeding the first pass without '
                        'posting, then going live')
            seed_first_pass = True
        else:
            LOG.error(
                'refusing to post from an empty database: the first pass '
                'would tweet every game already final in the polling window. '
                'Run with --seed once to backfill, then start with --live.')
            connection.close()
            return 1

    if args.seed:
        LOG.info('seed mode; games will be recorded but not tweeted')
    elif dry_run:
        LOG.info('print-only mode; nothing will be posted')

    options = Options(dry_run=dry_run, seed=args.seed, pace=args.pace,
                      shutdown=shutdown, limit=args.limit)

    if args.limit is not None:
        LOG.info('limit: will stop after %s game(s)', args.limit)

    try:
        while not shutdown.requested:
            dates = args.date or eastern_dates()

            try:
                if seed_first_pass:
                    seeding = Options(dry_run=True, seed=True, pace=0,
                                      shutdown=shutdown, limit=args.limit)
                    handled = run_once(connection, args.leagues, dates,
                                       seeding)
                    LOG.info('seeded %s game(s); posting from here on',
                             handled)
                    seed_first_pass = False
                else:
                    handled = run_once(connection, args.leagues, dates,
                                       options)
                    LOG.info('pass complete: %s new game(s)', handled)
            except Exception:  # noqa: BLE001 - the loop outlives any one pass
                LOG.exception('pass failed, continuing')

            if args.once or args.date or shutdown.requested:
                break

            # Sleep in short slices so a signal is noticed promptly.
            for _ in range(args.interval):
                if shutdown.requested:
                    break
                time.sleep(1)
    finally:
        totals = store.summary(connection)
        LOG.info('database totals: %s games, %s covers, %s pushes, %+.2f units',
                 totals['games'], totals['covers'] or 0,
                 totals['pushes'] or 0, totals['units'])
        connection.close()

    return 0


if __name__ == '__main__':
    sys.exit(main())
