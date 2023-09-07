"""Handles calculations for who covered and units won/lost"""


def did_fave_cover(team_a, team_b):
    """Determines who covered and the units won/lost"""

    dog = team_a if team_a['dog'] else team_b
    fav = team_a if team_b['dog'] else team_b
    spread = float(dog['spread'])

    covered = True if float(fav['score']) - \
        spread > float(dog['score']) else False

    if covered:
        return True, 1, fav, dog
    else:
        return False, (abs(fav['spread_price'])/100), fav, dog


def create_hashtag(team):
    """
    Creates a hashtag from the team name
    Hopefully drives tweet engagement
    TODO: Use the team's official hashtag opposed to this hacky solution
    """
    return f'#{team.split(" ")[-1]}'


def who_covered(odds, scores):
    """
    Takes the odds and scores to construct string of who covered
    Returns the string, number of covers, and units won/lost
    """
    check = '✅'
    cross = '❌'
    final_string = ''

    covers = 0
    total_units = 0
    total_games = 0

    for score in scores:
        odds_for_game = {}

        for game in odds:
            if game['id'] == score['id']:
                odds_for_game = game
                break

        score_for_game = score['scores']

        link_one = odds_for_game[score_for_game[0]['name']]
        link_two = odds_for_game[score_for_game[1]['name']]

        team_a = {}
        team_a = {
            'name': score_for_game[0]['name'],
            'score': score_for_game[0]['score'],
            'spread': link_one['spread'],
            'spread_price': link_one['spread_price'],
            'dog': link_one['dog']
        }

        team_b = {}
        team_b = {
            'name': score_for_game[1]['name'],
            'score': score_for_game[1]['score'],
            'spread': link_two['spread'],
            'spread_price': link_two['spread_price'],
            'dog': link_two['dog']
        }

        covered, units, fav, dog = did_fave_cover(team_a=team_a, team_b=team_b)

        total_games += 1

        if covered:
            covers += 1
            total_units += units
            final_string += f'{check}'
            final_string += f'{create_hashtag(fav["name"])} ({fav["spread"]}) vs {create_hashtag(dog["name"])}\n'
        else:
            total_units -= units
            final_string += f'{cross} '
            final_string += f'{create_hashtag(fav["name"])} ({fav["spread"]}) vs {create_hashtag(dog["name"])}\n'

    return final_string, covers, total_units, total_games
