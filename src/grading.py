"""Determines whether the favorite covered the spread, and the units it moved."""

COVER = 'cover'
PUSH = 'push'
NO_COVER = 'no_cover'


def payout(price):
    """Profit on a winning one-unit bet at the given American price.

    -110 returns 0.909, +150 returns 1.5. Defaults to standard -110 juice when
    a price is missing, which is what ESPN omits on the odd stale line.
    """

    if price is None:
        price = -110.0

    if price < 0:
        return 100.0 / abs(price)

    return price / 100.0


def evaluate(favorite_spread, favorite_score, underdog_score, favorite_price):
    """Grades a favorite's spread bet.

    ``favorite_spread`` is negative (e.g. -3.5). A one-unit bet on the favorite
    wins ``payout(price)``, loses 1.0, and pushes at exactly 0.
    """

    margin = favorite_score - underdog_score
    line = abs(favorite_spread)

    if margin > line:
        return COVER, payout(favorite_price)

    if margin == line:
        return PUSH, 0.0

    return NO_COVER, -1.0


def hashtag(team, league):
    """Builds the hashtag used in the tweet.

    NFL mascots are unique league-wide, so those read best. College mascots
    collide heavily (a dozen schools share Bulldogs), so college games use the
    school name instead.
    """

    if league == 'nfl':
        base = team.get('mascot') or team.get('location', '')
    else:
        base = team.get('location') or team.get('display_name', '')

    compact = ''.join(char for char in base if char.isalnum())

    return f'#{compact}' if compact else ''
