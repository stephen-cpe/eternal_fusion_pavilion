"""
Unit tests for utils.time_utils — pure functions, no DB required.
"""
from datetime import date, time

from utils.time_utils import get_dining_hours, generate_time_slots, is_valid_booking_time


class TestGetDiningHours:
    def test_tuesday_through_saturday_are_late_close(self):
        # Tuesday=1 ... Saturday=5
        for d in (
            date(2026, 8, 11),  # Tuesday
            date(2026, 8, 12),  # Wednesday
            date(2026, 8, 13),  # Thursday
            date(2026, 8, 14),  # Friday
            date(2026, 8, 15),  # Saturday
        ):
            start, end = get_dining_hours(d)
            assert start == time(17, 0)
            assert end == time(23, 0)

    def test_sunday_and_monday_are_early_close(self):
        for d in (
            date(2026, 8, 10),  # Monday
            date(2026, 8, 16),  # Sunday
        ):
            start, end = get_dining_hours(d)
            assert start == time(17, 0)
            assert end == time(21, 0)


class TestGenerateTimeSlots:
    def test_long_day_yields_twelve_slots(self):
        # Tuesday: 17:00-23:00 -> 12 slots of 30 min
        slots = generate_time_slots(date(2026, 8, 11))
        assert slots == [
            "17:00", "17:30", "18:00", "18:30", "19:00", "19:30",
            "20:00", "20:30", "21:00", "21:30", "22:00", "22:30",
        ]

    def test_short_day_yields_eight_slots(self):
        # Monday: 17:00-21:00 -> 8 slots
        slots = generate_time_slots(date(2026, 8, 10))
        assert slots == [
            "17:00", "17:30", "18:00", "18:30", "19:00", "19:30", "20:00", "20:30",
        ]

    def test_custom_interval(self):
        slots = generate_time_slots(date(2026, 8, 11), interval_minutes=60)
        assert slots == ["17:00", "18:00", "19:00", "20:00", "21:00", "22:00"]


class TestIsValidBookingTime:
    def test_within_dining_hours(self):
        assert is_valid_booking_time(date(2026, 8, 11), "19:00") is True

    def test_exactly_at_open(self):
        assert is_valid_booking_time(date(2026, 8, 11), "17:00") is True

    def test_exactly_at_close_is_invalid(self):
        # end_time is exclusive per implementation
        assert is_valid_booking_time(date(2026, 8, 11), "23:00") is False

    def test_before_open_is_invalid(self):
        assert is_valid_booking_time(date(2026, 8, 11), "16:30") is False

    def test_on_short_day_after_close(self):
        assert is_valid_booking_time(date(2026, 8, 10), "21:30") is False

    def test_malformed_time_returns_false(self):
        assert is_valid_booking_time(date(2026, 8, 11), "not-a-time") is False