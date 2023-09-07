"""Handles all tweet related functionality"""

import os
import tweepy
from dotenv import load_dotenv

load_dotenv()

ACCESS_TOKEN = os.getenv("TWITTER_ACCESS_TOKEN")
ACCESS_TOKEN_SECRET = os.getenv("TWITTER_ACCESS_TOKEN_SECRET")
CONSUMER_KEY = os.getenv("TWITTER_CONSUMER_KEY")
CONSUMER_SECRET = os.getenv("TWITTER_CONSUMER_SECRET")


def chunk_to_tweets(string):
    """Takes the full string and chunks it into tweets"""

    tot = 0
    tweets = []
    tweet = ''
    for s in string.split('\n'):
        tot += len(s)
        if tot > 200:
            tot = 0
            tweets.append(tweet)
            tweet = ''
        else:
            tweet += s + '\n'

    tweets.append(tweet)

    return tweets


def send_tweet(tweet):
    """Sends the Tweet string using Tweepy"""

    client = tweepy.Client(access_token=ACCESS_TOKEN, access_token_secret=ACCESS_TOKEN_SECRET,
                           consumer_key=CONSUMER_KEY, consumer_secret=CONSUMER_SECRET)

    client.create_tweet(text=tweet)

    return
