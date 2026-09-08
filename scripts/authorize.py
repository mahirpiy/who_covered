"""One-off PIN-based OAuth to get access tokens for the bot's X account.

The developer app lives on your personal X account, but the bot must post as
@ChalkReport. The app's consumer key/secret identify the *app*; the access
token/secret identify the *posting account*. This script runs the 3-legged
OAuth flow so you can issue an access token for @ChalkReport without moving
the app or the billing.

Before running: set the app's permissions to **Read and Write** in the X
developer portal. Authorizing under read-only permissions produces a token
that silently fails to post (403 on create_tweet), and fixing it means
regenerating and re-authorizing.

Usage:

    env/bin/python scripts/authorize.py

The tokens are written straight into .env. Nothing is printed unless you pass
--print, so they stay out of your terminal scrollback.
"""

import argparse
import os
import pathlib
import sys

from dotenv import load_dotenv

ENV_PATH = pathlib.Path(__file__).resolve().parents[1] / '.env'

CONSUMER_KEY_NAME = 'TWITTER_CONSUMER_KEY'
CONSUMER_SECRET_NAME = 'TWITTER_CONSUMER_SECRET'
ACCESS_TOKEN_NAME = 'TWITTER_ACCESS_TOKEN'
ACCESS_SECRET_NAME = 'TWITTER_ACCESS_TOKEN_SECRET'


def consumer_credentials():
    """Reads the app's consumer key/secret, prompting if they are not set."""

    load_dotenv(ENV_PATH)

    key = os.getenv(CONSUMER_KEY_NAME)
    secret = os.getenv(CONSUMER_SECRET_NAME)

    if not key:
        key = input('App consumer key (API Key): ').strip()
    if not secret:
        secret = input('App consumer secret (API Key Secret): ').strip()

    if not key or not secret:
        sys.exit('Consumer key and secret are both required.')

    return key, secret


def write_env(values):
    """Updates .env in place, replacing existing keys and appending new ones."""

    lines = []
    if ENV_PATH.exists():
        lines = ENV_PATH.read_text().splitlines()

    remaining = dict(values)
    updated = []

    for line in lines:
        name = line.split('=', 1)[0].strip()
        if name in remaining:
            updated.append(f'{name}={remaining.pop(name)}')
        else:
            updated.append(line)

    for name, value in remaining.items():
        updated.append(f'{name}={value}')

    ENV_PATH.write_text('\n'.join(updated) + '\n')

    # Tokens are account credentials; keep them off other users' eyes.
    ENV_PATH.chmod(0o600)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--print', dest='show', action='store_true',
                        help='print the tokens instead of writing .env')
    args = parser.parse_args()

    import tweepy

    key, secret = consumer_credentials()

    handler = tweepy.OAuth1UserHandler(key, secret, callback='oob')

    try:
        url = handler.get_authorization_url()
    except tweepy.TweepyException as error:
        sys.exit(f'Could not start the OAuth flow: {error}\n'
                 'Check that the consumer key/secret are correct and that '
                 'OAuth 1.0a is enabled for the app.')

    print()
    print('1. Open this URL in a browser where you are logged in as the BOT '
          'account:')
    print()
    print(f'   {url}')
    print()
    print('   If your personal account is the one logged in, use a private '
          'window and sign in as the bot first. Whichever account approves '
          'is the account the bot will post as.')
    print()

    pin = input('2. Paste the PIN shown after you approve: ').strip()

    if not pin:
        sys.exit('No PIN entered.')

    try:
        access_token, access_secret = handler.get_access_token(pin)
    except tweepy.TweepyException as error:
        sys.exit(f'Could not exchange the PIN: {error}')

    # Confirm which account these tokens actually belong to. This is the check
    # that catches the common mistake of approving while logged in as the
    # wrong account. Costs one read.
    client = tweepy.Client(
        consumer_key=key, consumer_secret=secret,
        access_token=access_token, access_token_secret=access_secret,
    )

    try:
        me = client.get_me(user_auth=True).data
        print(f'\nAuthorized as @{me.username} ({me.name})')
    except tweepy.TweepyException as error:
        print(f'\nGot tokens, but could not verify the account: {error}')
        me = None

    if args.show:
        print(f'\n{ACCESS_TOKEN_NAME}={access_token}')
        print(f'{ACCESS_SECRET_NAME}={access_secret}')
    else:
        write_env({
            CONSUMER_KEY_NAME: key,
            CONSUMER_SECRET_NAME: secret,
            ACCESS_TOKEN_NAME: access_token,
            ACCESS_SECRET_NAME: access_secret,
        })
        print(f'\nWrote all four credentials to {ENV_PATH} (mode 600).')

    if me is not None and me.username.lower() != 'chalkreport':
        print(f'\nWARNING: these tokens post as @{me.username}, not '
              '@ChalkReport. Re-run while logged in as the bot account.')


if __name__ == '__main__':
    main()
