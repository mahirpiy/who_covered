"""Checks the bot's X credentials before a live deploy.

Read-only by default: confirms tweepy loads, all four credentials are present,
and reports which account the tokens actually post as.

Read-only cannot prove the token has *write* scope -- a read-only token
authenticates fine and then fails with a 403 on the first tweet. Pass --post
to prove write access by publishing a throwaway tweet and immediately deleting
it. That posts publicly for a moment, so it is opt-in.
"""

import argparse
import os
import pathlib
import sys
from datetime import datetime

from dotenv import load_dotenv

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'src'))

load_dotenv(pathlib.Path(__file__).resolve().parents[1] / '.env')

import tweet  # noqa: E402  (needs the path set above)


def client():
    creds = tweet.credentials()
    if creds is None:
        missing = [n for n in tweet.CREDENTIAL_NAMES if not os.getenv(n)]
        sys.exit('Missing credentials: ' + ', '.join(missing))

    import tweepy

    return tweepy.Client(
        consumer_key=creds['TWITTER_CONSUMER_KEY'],
        consumer_secret=creds['TWITTER_CONSUMER_SECRET'],
        access_token=creds['TWITTER_ACCESS_TOKEN'],
        access_token_secret=creds['TWITTER_ACCESS_TOKEN_SECRET'],
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--post', action='store_true',
                        help='publish and delete a throwaway tweet to prove '
                             'write scope')
    parser.add_argument('--latest', type=int, metavar='N', default=None,
                        help='show the N most recent tweets on the account, '
                             'to confirm a deploy actually posted')
    args = parser.parse_args()

    import tweepy

    print(f'tweepy {tweepy.__version__}')

    api = client()

    me = api.get_me(user_auth=True).data
    print(f'authenticated as @{me.username} ({me.name})')

    if me.username.lower() != 'chalkreport':
        print(f'\nWARNING: tokens post as @{me.username}, not @ChalkReport.')

    if args.latest:
        recent = api.get_users_tweets(
            me.id, max_results=max(5, args.latest), user_auth=True,
            tweet_fields=['created_at'])

        posts = recent.data or []
        if not posts:
            print('\nNo tweets on the account yet.')
        for post in posts[:args.latest]:
            print(f'\n[{post.created_at:%Y-%m-%d %H:%M UTC}] '
                  f'https://x.com/{me.username}/status/{post.id}')
            print(post.text)
        return

    if not args.post:
        print('\nRead check passed. This does NOT prove write scope -- '
              'rerun with --post to confirm the bot can actually tweet.')
        return

    text = f'setup check {datetime.now():%Y-%m-%d %H:%M:%S}'

    try:
        created = api.create_tweet(text=text)
    except tweepy.Forbidden as error:
        sys.exit(f'\nWRITE FAILED (403): {error}\n'
                 'The access token is read-only. Set the app to Read and '
                 'Write in the developer portal, regenerate, and re-run '
                 'scripts/authorize.py.')

    tweet_id = created.data['id']
    print(f'posted test tweet {tweet_id}')

    api.delete_tweet(tweet_id)
    print('deleted it. Write access confirmed.')


if __name__ == '__main__':
    main()
