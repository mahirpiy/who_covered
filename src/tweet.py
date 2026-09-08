"""Tweet composition and delivery.

Delivery defaults to print-only. Actually posting requires both the --live
flag and a full set of Twitter credentials in the environment; without those
the bot prints and records the tweet without sending it.
"""

import logging
import os

from dotenv import load_dotenv

load_dotenv()

LOG = logging.getLogger(__name__)

MAX_TWEET_LENGTH = 280

CREDENTIAL_NAMES = (
    'TWITTER_ACCESS_TOKEN',
    'TWITTER_ACCESS_TOKEN_SECRET',
    'TWITTER_CONSUMER_KEY',
    'TWITTER_CONSUMER_SECRET',
)


def preflight():
    """Verifies posting is actually possible, before the first game finishes.

    tweepy is imported lazily in send_tweet so the dry-run path has no hard
    dependency on it. That means an unusable install would otherwise surface
    only when the first game goes final, hours into a deploy. Called at
    startup whenever --live is set.
    """

    try:
        import tweepy
    except ImportError as error:
        raise RuntimeError(
            f'cannot import tweepy, so posting would fail: {error}') from error

    missing = [name for name in CREDENTIAL_NAMES if not os.getenv(name)]
    if missing:
        raise RuntimeError(
            'missing Twitter credentials: ' + ', '.join(missing))

    LOG.info('preflight ok: tweepy %s, all credentials present',
             tweepy.__version__)


def credentials():
    """Returns the four Twitter credentials, or None if any are missing."""

    values = {name: os.getenv(name) for name in CREDENTIAL_NAMES}

    if not all(values.values()):
        return None

    return values


def send_tweet(text, dry_run=True):
    """Sends a tweet, or prints it when running dry.

    Returns True if the tweet was actually posted.
    """

    if len(text) > MAX_TWEET_LENGTH:
        LOG.error('tweet is %s chars, over the %s limit -- skipping:\n%s',
                  len(text), MAX_TWEET_LENGTH, text)
        return False

    if dry_run:
        print('-' * 40)
        print(text)
        print(f'[dry run | {len(text)} chars]')
        return False

    creds = credentials()
    if creds is None:
        missing = [n for n in CREDENTIAL_NAMES if not os.getenv(n)]
        LOG.error('cannot post, missing credentials: %s', ', '.join(missing))
        return False

    # Imported lazily so the dry-run path has no hard dependency on tweepy.
    import tweepy

    client = tweepy.Client(
        access_token=creds['TWITTER_ACCESS_TOKEN'],
        access_token_secret=creds['TWITTER_ACCESS_TOKEN_SECRET'],
        consumer_key=creds['TWITTER_CONSUMER_KEY'],
        consumer_secret=creds['TWITTER_CONSUMER_SECRET'],
    )

    client.create_tweet(text=text)
    LOG.info('posted tweet (%s chars)', len(text))

    return True
