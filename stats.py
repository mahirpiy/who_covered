def day_performance(covers, total_games, total_units):
    """
    Uses the calculated data to create a performance string
    Provides a summary of the day's performance
    """

    up = '📈'
    down = '📉'
    shake = '🤝'
    fire = '🔥'
    ice = '🧊'
    equal = '🤷‍♂️'

    performance_string = ''

    percentage = covers / total_games

    rounded_total_units = round(total_units, 2)
    if percentage > 0.6:
        performance_string += f'{fire} {covers}/{total_games} favorites covered\n'
    elif percentage < 0.4:
        performance_string += f'{ice} {covers}/{total_games} favorites covered\n'
    else:
        performance_string += f'{shake} {covers}/{total_games} favorites covered\n'

    if total_units > 0.5:
        performance_string += f'{up} +{rounded_total_units} units'
    elif total_units < -0.5:
        performance_string += f'{down} {rounded_total_units} units'
    elif total_units == 0:
        performance_string += f'{shake} {rounded_total_units} units\nPushes are wins'
    else:
        performance_string += f'{equal} {rounded_total_units} units'

    return performance_string
