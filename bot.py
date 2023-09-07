"""Handler for the bot"""

from odds import get_odds
from request import odds_request, scores_request
from scores import clean_scores
from who_covered import who_covered
from stats import day_performance
from tweet import chunk_to_tweets, send_tweet


def run_bot():
    """
    Runs the bot
    Gets and cleans the data
    Creates and sends the tweets
    """

    api_scores = scores_request()
    api_odds = odds_request('2023-09-05T17:00:00Z')
    scores = clean_scores(api_scores)
    odds = get_odds(api_odds)

    final_string, covers, total_units, total_games = who_covered(odds, scores)

    header = '⚾ MLB 9/5/23 ⚾'

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
    run_bot()
