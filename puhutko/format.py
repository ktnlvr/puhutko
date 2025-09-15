from datetime import datetime


from datetime import datetime


def relative_time(dt: datetime) -> str:
    now = datetime.now()
    delta = dt - now
    seconds = int(delta.total_seconds())

    if seconds < 0:
        seconds = -seconds
        if seconds < 120:
            return "<2 minutes ago"
        if seconds < 3600:
            mins = (seconds + 30) // 60
            return f"{mins} minutes ago"
        if seconds < 86400:
            hours = (seconds + 1800) // 3600
            return f"{hours} hours ago"
        days = (seconds + 43200) // 86400
        return f"{days} days ago"

    if seconds < 120:
        return "<2 minutes"
    if seconds < 3600:
        mins = (seconds + 30) // 60
        return f"in {mins} minutes"
    if seconds < 86400:
        hours = (seconds + 1800) // 3600
        return f"in {hours} hours"
    days = (seconds + 43200) // 86400

    return f"in {days} days"
