"""Handler for the bot"""

import sys
from datetime import datetime
from odds import get_odds
from request import odds_request, scores_request
from scores import clean_scores
from who_covered import who_covered
from stats import day_performance
from tweet import chunk_to_tweets, send_tweet

SPORT_TO_EMOJI = {
    'mlb': '⚾',
    'nfl': '🏈',
    'nba': '🏀',
    'nhl': '🏒',
}


def get_timestamp():
    """
    Constructs timestamp for request
    """
    now = datetime.now()
    month = now.month if now.month > 9 else f'0{now.month}'
    day = now.day if now.day > 9 else f'0{now.day}'
    timestamp = f'{now.year}-{month}-{day}T17:00:00Z'

    return month, day, timestamp


def get_data(timestamp, sport):
    """
    Gets the odds and scores data from odds api
    """

    api_scores = scores_request(sport)
    api_odds = odds_request(timestamp, sport)

    scores = clean_scores(api_scores)
    odds = get_odds(api_odds)

    return scores, odds


def create_tweets(odds, scores):
    """
    Takes the odds and scores and constructs the tweets
    """
    who_covered_string, covers, total_units, total_games = who_covered(
        odds, scores)

    performance = day_performance(covers, total_games, total_units)

    tweets = chunk_to_tweets(who_covered_string)

    return tweets, performance, total_games


def send_tweets(tweets, header: str, performance: str, total_games):
    """
    Takes the chunked tweets and sends them
    """
    for idx, tweet in enumerate(tweets):
        final_tweet = ''
        final_tweet += header + '\n'

        for sub_string in tweet.split('\n'):
            if sub_string in ('', '\n', ' '):
                continue

            final_tweet += sub_string + '\n'

        if len(tweets) > 1:
            final_tweet += f'\n({idx + 1}/{len(tweets)})'

        send_tweet(final_tweet)

    if total_games > 3:
        performance_tweet = f'{header}\n📊 DAY PERFORMANCE 📊\n\n{performance}'
        send_tweet(performance_tweet)


def run_bot(sport: str):
    """
    Main function for bot
    Gets the data, creates the tweets, and sends them
    """
    month, day, timestamp = get_timestamp()

    header = f'{SPORT_TO_EMOJI[sport]} {sport.upper()} {month}/{day} {SPORT_TO_EMOJI[sport]}\n'

    scores, odds = get_data(timestamp, sport)

    tweets, performance, total_games = create_tweets(odds, scores)

    send_tweets(tweets, header, performance, total_games)


if __name__ == '__main__':
    SPORT = sys.argv[1]
    run_bot(SPORT)
