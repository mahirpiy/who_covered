"""Parser for the odds API"""


def get_odds(response):
    """
    Takes the odds from API response and sanitizes them 
    Returns a list of games with their spreads and prices
    """

    games = []

    for event in response:
        odds_data = {}

        dk_data = [bookmaker for bookmaker in event['bookmakers']
                   if bookmaker['key'] == 'draftkings']
        fd_data = [bookmaker for bookmaker in event['bookmakers']
                   if bookmaker['key'] == 'fanduel']

        if len(dk_data) > 0:
            odds_data = dk_data[0]
        elif len(fd_data) > 0:
            odds_data = fd_data[0]
        else:
            continue

        for market in odds_data['markets']:
            if market['key'] == 'spreads':
                spreads = [{outcome['name']: outcome['point']}
                           for outcome in market['outcomes']]
                spread_price = [{outcome['name']: outcome['price']}
                                for outcome in market['outcomes']]

        fave = min(spreads, key=lambda x: list(x.values())[0])
        dog = max(spreads, key=lambda x: list(x.values())[0])

        fave_team = list(fave.keys())[0]
        dog_team = list(dog.keys())[0]

        for spread in spreads:
            if list(spread.keys())[0] == fave_team:
                fave_spread = list(spread.values())[0]
            elif list(spread.keys())[0] == dog_team:
                dog_spread = list(spread.values())[0]

        for price in spread_price:
            if list(price.keys())[0] == fave_team:
                fave_spread_price = list(price.values())[0]
            elif list(price.keys())[0] == dog_team:
                dog_spread_price = list(price.values())[0]

        game = {}
        game['id'] = event['id']
        game[fave_team] = {
            'spread': fave_spread,
            'spread_price': fave_spread_price,
            'dog': False
        }
        game[dog_team] = {
            'spread': dog_spread,
            'spread_price': dog_spread_price,
            'dog': True
        }

        games.append(game)

    return games
