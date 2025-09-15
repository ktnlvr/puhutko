from .card import Card


def sm2_next(card, quality: int) -> tuple[float, float, int]:
    assert 0 <= quality <= 5, "Quality must be between 0 and 5"

    # Extract current state
    ef = card.ease_factor
    reps = card.repetitions
    interval = card.interval

    # Learning phase (card not yet graduated)
    if reps == 0:
        if quality < 3:
            # Failed: retry after 10 minutes, keep in learning phase
            interval_days = 10 / 1440  # 10 minutes
            reps = 0
        elif quality == 3:
            # Moderate: move to next learning step (1 hour)
            interval_days = 1 / 24  # 1 hour
            reps = 1
        elif quality == 4:
            # Good: move to next learning step (6 hours)
            interval_days = 6 / 24  # 6 hours
            reps = 1
        else:  # quality == 5
            # Easy: graduate to 1 day interval
            interval_days = 1.0
            reps = 1

    # Review phase (card has been graduated)
    else:
        if quality < 3:
            # Failed: reset to learning phase with 10-minute interval
            reps = 0
            interval_days = 10 / 1440
            # Reduce ease factor more significantly for failures
            ef = max(1.3, ef - 0.2)
        else:
            # Calculate next interval based on current status
            if reps == 1:
                interval_days = 1.0  # First review after graduation
            elif reps == 2:
                interval_days = 6.0  # Second review
            else:
                # For mature cards, use the standard SM-2 interval formula
                interval_days = interval * ef

            reps += 1

    # Update ease factor with smoother progression
    if quality >= 3:
        # Smoother EF adjustment based on quality
        ef_adjustment = 0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02)
        ef = ef + ef_adjustment
    else:
        # Additional penalty for failing cards
        ef = ef - 0.2

    # Clamp ease factor to reasonable bounds
    ef = max(1.3, min(ef, 2.5))

    # Ensure interval is at least 1 day for graduated cards
    if reps > 1 and interval_days < 1.0:
        interval_days = 1.0

    return float(interval_days), float(ef), int(reps)
