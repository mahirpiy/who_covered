"""Handles getting and formatting the scores"""


def clean_scores(scores):
    """Takes the scores from API response and sanitizes them"""

    cleaned_scores = []
    for score in scores:
        if not score['completed']:
            continue

        reduced = score['scores']

        game = {}
        game['id'] = score['id']
        game['scores'] = reduced

        cleaned_scores.append(game)

    return cleaned_scores
