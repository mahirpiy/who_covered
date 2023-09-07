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
}


def run_bot(sport: str):
    """
    Runs the bot
    Gets and cleans the data
    Creates and sends the tweets
    """
    now = datetime.now()
    month = now.month if now.month > 9 else f'0{now.month}'
    day = now.day if now.day > 9 else f'0{now.day}'
    timestamp = f'{now.year}-{month}-{day}T17:00:00Z'

    api_scores = scores_request(sport)
    api_odds = odds_request(timestamp, sport)
    scores = clean_scores(api_scores)
    odds = get_odds(api_odds)

    final_string, covers, total_units, total_games = who_covered(odds, scores)

    header = f'{SPORT_TO_EMOJI[sport]} {sport.upper()} {now.day}/{now.month} {SPORT_TO_EMOJI[sport]}'

    performance_string = day_performance(covers, total_games, total_units)

    tweets = chunk_to_tweets(final_string)

    for idx, tweet in enumerate(tweets):
        final_tweet = ''
        final_tweet += header + '\n'

        for sub_string in tweet.split('\n'):
            if sub_string in ('', '\n', ' '):
                continue

            final_tweet += sub_string + '\n'

        final_tweet += f'\n({idx + 1}/{len(tweets)})'
        send_tweet(final_tweet)

    performance_tweet = f'{header}\n📊 DAY PERFORMANCE 📊\n\n{performance_string}'

    send_tweet(performance_tweet)


if __name__ == '__main__':
    SPORT = sys.argv[1]
    run_bot(SPORT)
