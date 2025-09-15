from .card import Card


def sm2_next(card: Card, quality: int) -> tuple[float, float, int]:
    assert 0 <= quality <= 5
    ef = card.ease_factor
    reps = card.repetitions

    if reps == 0:
        if quality < 3:
            # failed: retry in 10 minutes, still a learning card
            interval_days = 10 / 1440  # 10 minutes
            reps = 0
        elif quality == 4:
            # correct but not perfect: go to second learning step (10m), mark as 1 repetition
            interval_days = 10 / 1440
            reps = 1
        else:  # quality == 5
            # easy -> graduate to 1 day interval
            interval_days = 1.0
            reps = 1

    else:
        if quality < 3:
            # failed: reset repetitions, put into short relearning (we'll use 10 minutes)
            reps = 0
            interval_days = 10 / 1440
        else:
            if reps == 0:
                interval_days = 1.0
            elif reps == 1:
                interval_days = 6.0
            else:
                interval_days = max(1.0, round(card.interval * ef))
            reps = reps + 1

    # update ease factor
    ef = ef + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
    if ef < 1.3:
        ef = 1.3

    return float(interval_days), float(ef), int(reps)
