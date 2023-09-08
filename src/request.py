"""Handles Requests to Odds API"""

import os
import requests
from dotenv import load_dotenv

load_dotenv()


API_KEY = os.environ.get('ODDS_API_KEY_V2')
BASE_ODDS_URI = 'https://api.the-odds-api.com/v4/sports/'
ODDS_QUERY_URI = f'/odds-history/?apiKey={API_KEY}&regions=us&markets=spreads&oddsFormat=american&date='
SCORES_QUERY_URI = f'/scores/?daysFrom=1&apiKey={API_KEY}'

SPORT_TO_SPORT_CODE = {
    "mlb": "baseball_mlb",
    "nfl": "americanfootball_nfl",
    "nba": "basketball_nba",
    "nhl": "icehockey_nhl",
}


def odds_request(timestamp, sport):
    """Makes request to get odds for the day"""

    request_url = BASE_ODDS_URI + \
        SPORT_TO_SPORT_CODE[sport] + ODDS_QUERY_URI + timestamp

    odds_data = requests.get(request_url, timeout=100).json()

    return odds_data['data']


def scores_request(sport):
    """Makes request to get the scores for the day"""

    request_url = BASE_ODDS_URI + SPORT_TO_SPORT_CODE[sport] + SCORES_QUERY_URI

    scores_data = requests.get(request_url, timeout=100).json()

    return scores_data
