"""
Time and scheduling utilities
"""
from datetime import datetime, time, timedelta
from typing import List, Tuple

def get_dining_hours(date: datetime.date) -> Tuple[time, time]:
    """
    Get dining hours for a given date based on day of week.
    Tuesday-Saturday: 5:00 PM - 11:00 PM
    Sunday-Monday: 5:00 PM - 9:00 PM
    
    Returns (start_time, end_time)
    """
    weekday = date.weekday()  # Monday=0, Sunday=6
    
    start_time = time(17, 0)  # 5:00 PM
    
    # Tuesday (1) through Saturday (5)
    if 1 <= weekday <= 5:
        end_time = time(23, 0)  # 11:00 PM
    else:  # Sunday (6) and Monday (0)
        end_time = time(21, 0)  # 9:00 PM
    
    return start_time, end_time


def generate_time_slots(date: datetime.date, interval_minutes: int = 30) -> List[str]:
    """
    Generate available time slots for a given date.
    Default interval is 30 minutes.
    
    Returns list of time strings in HH:MM format.
    """
    start_time, end_time = get_dining_hours(date)
    
    slots = []
    current = datetime.combine(date, start_time)
    end_dt = datetime.combine(date, end_time)
    
    while current < end_dt:
        slots.append(current.strftime('%H:%M'))
        current += timedelta(minutes=interval_minutes)
    
    return slots


def is_valid_booking_time(date: datetime.date, time_str: str) -> bool:
    """
    Check if a given time is within valid dining hours for the date.
    """
    try:
        booking_time = datetime.strptime(time_str, '%H:%M').time()
        start_time, end_time = get_dining_hours(date)
        return start_time <= booking_time < end_time
    except ValueError:
        return False
