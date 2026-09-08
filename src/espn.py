"""Client for ESPN's public (undocumented) scoreboard and odds endpoints.

No API key required. Two endpoints are used:

* ``site.api.espn.com`` scoreboard -- every game for a date, with status and
  final scores. One request covers a whole slate.
* ``sports.core.api.espn.com`` odds -- per-event betting lines. The ``close``
  block holds the closing spread and price and persists after the game ends;
  it is null before kickoff, where ``current`` holds the live line instead.

These endpoints are unofficial and carry no stability guarantee, so every
parser here raises on unexpected shapes rather than guessing.
"""

import logging
import time

import requests

LOG = logging.getLogger(__name__)

SITE_BASE = 'https://site.api.espn.com/apis/site/v2/sports/football'
CORE_BASE = 'https://sports.core.api.espn.com/v2/sports/football/leagues'

# Our short sport names mapped to ESPN's league path segment.
LEAGUE_PATH = {
    'nfl': 'nfl',
    'cfb': 'college-football',
}

TIMEOUT = 20
RETRIES = 3
BACKOFF = 2.0


class EspnError(RuntimeError):
    """Raised when ESPN returns something we cannot parse."""


def _get(url, params=None):
    """GET with a small retry/backoff, returning parsed JSON."""

    last_error = None

    for attempt in range(RETRIES):
        try:
            response = requests.get(url, params=params, timeout=TIMEOUT)
            response.raise_for_status()
            return response.json()
        except (requests.RequestException, ValueError) as error:
            last_error = error
            if attempt < RETRIES - 1:
                sleep_for = BACKOFF ** attempt
                LOG.warning('request failed (%s), retrying in %.1fs: %s',
                            attempt + 1, sleep_for, error)
                time.sleep(sleep_for)

    raise EspnError(f'GET {url} failed after {RETRIES} attempts: {last_error}')


def scoreboard(league, date):
    """Returns the raw event list for one league on one date.

    ``date`` is a ``YYYYMMDD`` string in US Eastern, which is how ESPN buckets
    its slates. No group filter is applied, so all divisions are included.
    """

    url = f'{SITE_BASE}/{LEAGUE_PATH[league]}/scoreboard'
    payload = _get(url, params={'dates': date, 'limit': 500})

    return payload.get('events', [])


def parse_event(event):
    """Pulls the fields we care about out of a scoreboard event.

    Returns None when the game is not final or is missing a score, which is the
    normal case for anything still in progress.
    """

    status = event.get('status', {}).get('type', {})
    if not status.get('completed'):
        return None

    competition = event['competitions'][0]

    home = away = None
    for competitor in competition.get('competitors', []):
        side = competitor.get('homeAway')
        if side == 'home':
            home = competitor
        elif side == 'away':
            away = competitor

    if home is None or away is None:
        LOG.warning('event %s missing home/away competitor', event.get('id'))
        return None

    try:
        home_score = int(home['score'])
        away_score = int(away['score'])
    except (KeyError, TypeError, ValueError):
        LOG.warning('event %s completed but has no usable score', event.get('id'))
        return None

    return {
        'event_id': str(event['id']),
        'competition_id': str(competition['id']),
        'short_name': event.get('shortName', ''),
        'start_time': event.get('date', ''),
        'home': _team(home),
        'away': _team(away),
        'home_score': home_score,
        'away_score': away_score,
    }


def _team(competitor):
    """Flattens a competitor's team block into the names we display."""

    team = competitor.get('team', {})

    return {
        'id': str(team.get('id', '')),
        'location': team.get('location', ''),
        'mascot': team.get('name', ''),
        'abbreviation': team.get('abbreviation', ''),
        'display_name': team.get('displayName', ''),
    }


def game_odds(league, event_id, competition_id=None):
    """Returns the closing spread and price for one event, or None.

    ESPN quotes the spread from the home team's perspective. We prefer the
    ``close`` block; ``current`` is the fallback for the window where a game is
    final but the closing line has not been stamped yet.
    """

    competition_id = competition_id or event_id
    url = (f'{CORE_BASE}/{LEAGUE_PATH[league]}/events/{event_id}'
           f'/competitions/{competition_id}/odds')

    try:
        payload = _get(url)
    except EspnError as error:
        LOG.warning('no odds for event %s: %s', event_id, error)
        return None

    for item in payload.get('items', []):
        parsed = _parse_odds_item(item)
        if parsed is not None:
            return parsed

    LOG.warning('event %s returned no usable spread', event_id)

    return None


def _parse_odds_item(item):
    """Extracts (home spread, home price, favorite side) from one odds entry."""

    home_odds = item.get('homeTeamOdds') or {}
    away_odds = item.get('awayTeamOdds') or {}

    for block in ('close', 'current'):
        spread = _american(home_odds.get(block, {}).get('pointSpread', {}))
        price = _american(home_odds.get(block, {}).get('spread', {}))

        if spread is None:
            continue

        # ESPN flags the favorite explicitly, which avoids having to infer it
        # from the spread and sidesteps the pick'em ambiguity entirely.
        if home_odds.get('favorite'):
            favorite = 'home'
        elif away_odds.get('favorite'):
            favorite = 'away'
        elif spread < 0:
            favorite = 'home'
        elif spread > 0:
            favorite = 'away'
        else:
            # True pick'em with no flag: nominate home so the cover check
            # reduces to a straight win/loss/tie.
            favorite = 'home'

        return {
            'home_spread': spread,
            'home_price': price,
            'favorite': favorite,
            'provider': item.get('provider', {}).get('name', 'unknown'),
            'source': block,
        }

    return None


def _american(block):
    """Parses ESPN's ``"+3.5"`` / ``"-120"`` American-odds strings to float."""

    value = block.get('american')
    if value is None:
        return None

    try:
        return float(str(value).replace('+', ''))
    except ValueError:
        return None
