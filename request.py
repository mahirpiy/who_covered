"""Handles Requests to Odds API"""

import os
import requests
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()


API_KEY = os.environ.get('ODDS_API_KEY_V2')
BASE_API_URI = 'https://api.the-odds-api.com/v4/sports/'
SPORT_CODE = 'baseball_mlb'
ODDS_QUERY_URI = f'/odds-history/?apiKey={API_KEY}&regions=us&markets=spreads&oddsFormat=american&date='
SCORES_QUERY_URI = f'/scores/?daysFrom=1&apiKey={API_KEY}'


def odds_request(timestamp):
    """Makes request to get odds for the day"""

    request_url = BASE_API_URI + SPORT_CODE + ODDS_QUERY_URI + timestamp

    odds_data = requests.get(request_url, timeout=100).json()

    return odds_data['data']


def scores_request():
    """Makes request to get the scores for the day"""

    request_url = BASE_API_URI + SPORT_CODE + SCORES_QUERY_URI

    scores_data = requests.get(request_url, timeout=100).json()

    return scores_data


def get_data():
    """Gets the data from the API"""

    return


if __name__ == '__main__':
    odds_request('2023-08-28T17:00:00Z')
