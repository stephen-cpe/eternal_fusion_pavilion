"""
Unit tests for utils.room_assignment — use FakeConnection to assert on the
*logic* (weight formula, filter conditions, exclude_id propagation, soft/hard
block branching) without standing up a real Postgres.

These tests do NOT exercise the actual SQL dialect; they validate the Python
control flow and that the right query/params are emitted.
"""
import pytest

from utils.room_assignment import (
    calculate_room_occupancy,
    calculate_location_occupancy,
    check_room_blocks,
    check_location_blocks,
    get_candidate_rooms,
    weighted_random_room_selection,
    generate_reservation_number,
    validate_reservation_constraints,
)
from tests.fake_db import FakeConnection, FakeRoomRow


# --------------------------------------------------------------------------- #
# calculate_room_occupancy                                                     #
# --------------------------------------------------------------------------- #
class TestCalculateRoomOccupancy:
    def test_returns_zero_when_no_reservations(self, monkeypatch):
        conn = FakeConnection()
        conn.queue_results([(0,)])  # SUM -> 0
        assert calculate_room_occupancy(conn, 1, "2026-08-11", "19:00") == 0

    def test_returns_sum_party_size(self):
        conn = FakeConnection()
        conn.queue_results([(7,)])  # SUM -> 7
        assert calculate_room_occupancy(conn, 1, "2026-08-11", "19:00") == 7

    def test_exclude_id_appends_to_query_and_params(self):
        conn = FakeConnection()
        conn.queue_results([(0,)])
        calculate_room_occupancy(conn, 1, "2026-08-11", "19:00", exclude_id=42)
        query, params = conn.executed[-1]
        assert "AND id != %s" in query
        assert 42 in params


# --------------------------------------------------------------------------- #
# calculate_location_occupancy                                                 #
# --------------------------------------------------------------------------- #
class TestCalculateLocationOccupancy:
    def test_returns_guests_and_reservations_tuple(self):
        conn = FakeConnection()
        conn.queue_results([(12, 3)])  # (total_guests, total_reservations)
        guests, res = calculate_location_occupancy(conn, 1, "2026-08-11", "19:00")
        assert guests == 12
        assert res == 3

    def test_exclude_id_propagates(self):
        conn = FakeConnection()
        conn.queue_results([(0, 0)])
        calculate_location_occupancy(
            conn, 1, "2026-08-11", "19:00", exclude_id=99
        )
        query, params = conn.executed[-1]
        assert "AND id != %s" in query
        assert 99 in params


# --------------------------------------------------------------------------- #
# check_room_blocks / check_location_blocks                                    #
# --------------------------------------------------------------------------- #
class TestCheckRoomBlocks:
    def test_blocked_returns_true(self):
        conn = FakeConnection()
        conn.queue_results([(1,)])  # COUNT(*) > 0
        assert check_room_blocks(conn, 1, "2026-08-11", "19:00", 60, "hard") is True

    def test_not_blocked_returns_false(self):
        conn = FakeConnection()
        conn.queue_result_set([(0,)])  # COUNT(*) = 0
        assert check_room_blocks(conn, 1, "2026-08-11", "19:00", 60, "soft") is False

    def test_block_type_is_parametrized(self):
        conn = FakeConnection()
        conn.queue_result_set([(0,)])
        check_room_blocks(conn, 1, "2026-08-11", "19:00", 60, "soft")
        _, params = conn.executed[-1]
        assert "soft" in params

    def test_all_day_block_query_uses_equality_branch(self):
        """A block with start_time == end_time must use the all-day branch."""
        conn = FakeConnection()
        conn.queue_result_set([(1,)])  # COUNT(*) = 1 -> blocked
        check_room_blocks(conn, 1, "2026-08-11", "19:00", 60, "hard")
        query, _ = conn.executed[-1]
        # The all-day condition must be present so 00:00-00:00 blocks match.
        assert "start_time = end_time" in query


class TestCheckLocationBlocks:
    def test_location_block_returns_true(self):
        conn = FakeConnection()
        conn.queue_results([(1,)])
        assert check_location_blocks(conn, 1, "2026-08-11", "19:00") is True

    def test_query_filters_room_id_null_and_hard(self):
        conn = FakeConnection()
        conn.queue_result_set([(0,)])
        check_location_blocks(conn, 1, "2026-08-11", "19:00")
        query, _ = conn.executed[-1]
        assert "room_id IS NULL" in query
        assert "block_type = 'hard'" in query

    def test_all_day_block_query_uses_equality_branch(self):
        """A location all-day block (00:00-00:00) must match any reservation time."""
        conn = FakeConnection()
        conn.queue_result_set([(1,)])
        assert check_location_blocks(conn, 1, "2026-08-11", "19:00") is True
        query, _ = conn.executed[-1]
        assert "start_time = end_time" in query


# --------------------------------------------------------------------------- #
# get_candidate_rooms                                                          #
# --------------------------------------------------------------------------- #
class TestGetCandidateRooms:
    def test_filters_out_hard_blocked_room(self):
        """
        Setup two rooms; the first is hard-blocked (check_room_blocks -> True),
        so only the second should appear as a candidate.
        """
        conn = FakeConnection()

        # 1) SELECT id, code, name, max_capacity FROM rooms -> two rooms (fetchall)
        conn.queue_result_set([
            FakeRoomRow.make(1, "R1", "Room One", 30),
            FakeRoomRow.make(2, "R2", "Room Two", 30),
        ])
        # 2) check_room_blocks(room 1, 'hard') -> True (blocked)
        conn.queue_result_set([(1,)])
        # 3) For room 2: check_room_blocks(room 2, 'hard') -> False (not blocked)
        conn.queue_result_set([(0,)])
        # 4) calculate_room_occupancy(room 2) -> 0
        conn.queue_result_set([(0,)])
        # 5) reservation_count for room 2 -> 0
        conn.queue_result_set([(0,)])

        candidates = get_candidate_rooms(conn, 1, "2026-08-11", "19:00", 4, 60)
        assert len(candidates) == 1
        assert candidates[0]["id"] == 2

    def test_filters_out_room_without_capacity(self):
        """A room whose available_capacity < party_size is excluded."""
        conn = FakeConnection()

        conn.queue_result_set([FakeRoomRow.make(1, "R1", "Room One", 30)])
        # Not hard-blocked
        conn.queue_result_set([(0,)])
        # Already 28 in the room -> only 2 left; party is 4 -> excluded
        conn.queue_result_set([(28,)])

        candidates = get_candidate_rooms(conn, 1, "2026-08-11", "19:00", 4, 60)
        assert candidates == []

    def test_weight_formula(self):
        """weight = (available_capacity * 1000) + (100 - reservation_count)."""
        conn = FakeConnection()

        conn.queue_result_set([FakeRoomRow.make(1, "R1", "Room One", 30)])
        conn.queue_result_set([(0,)])  # not blocked
        conn.queue_result_set([(10,)])  # occupancy 10 -> available 20
        conn.queue_result_set([(2,)])  # reservation_count 2

        candidates = get_candidate_rooms(conn, 1, "2026-08-11", "19:00", 5, 60)
        assert len(candidates) == 1
        # weight = (20 * 1000) + (100 - 2) = 20098
        assert candidates[0]["weight"] == 20098


# --------------------------------------------------------------------------- #
# weighted_random_room_selection                                               #
# --------------------------------------------------------------------------- #
class TestWeightedRandomRoomSelection:
    def test_returns_none_when_no_candidates(self, monkeypatch):
        conn = FakeConnection()
        # No rooms at all
        conn.queue_results([])  # SELECT rooms -> empty
        assert weighted_random_room_selection(conn, 1, "2026-08-11", "19:00", 4, 60) is None

    def test_returns_a_candidate_when_one_available(self):
        conn = FakeConnection()
        conn.queue_result_set([FakeRoomRow.make(5, "R5", "Room Five", 30)])
        conn.queue_result_set([(0,)])  # not blocked
        conn.queue_result_set([(0,)])  # occupancy 0
        conn.queue_result_set([(0,)])  # reservation_count 0

        selected = weighted_random_room_selection(conn, 1, "2026-08-11", "19:00", 4, 60)
        assert selected is not None
        assert selected["id"] == 5


# --------------------------------------------------------------------------- #
# generate_reservation_number                                                 #
# --------------------------------------------------------------------------- #
class TestGenerateReservationNumber:
    def test_format_is_LOC_DASH_5CHARS(self):
        import re
        rn = generate_reservation_number("JPN")
        assert re.match(r"^JPN-[A-Z0-9]{5}$", rn), f"Unexpected format: {rn}"

    def test_includes_location_code(self):
        rn = generate_reservation_number("ITA")
        assert rn.startswith("ITA-")

    def test_randomness(self):
        # Extremely unlikely to collide with 36^5 space, but we only assert
        # that two calls produce *different* values (collision prob ~1/60M).
        nums = {generate_reservation_number("ESP") for _ in range(20)}
        assert len(nums) > 1


# --------------------------------------------------------------------------- #
# validate_reservation_constraints                                             #
# --------------------------------------------------------------------------- #
class TestValidateReservationConstraints:
    def test_public_party_size_below_1_is_invalid(self):
        conn = FakeConnection()
        ok, msg = validate_reservation_constraints(
            conn, 1, "2026-08-11", "19:00", 0, 60, is_admin=False
        )
        assert ok is False
        assert "1 and 12" in msg

    def test_public_party_size_above_12_is_invalid(self):
        conn = FakeConnection()
        ok, msg = validate_reservation_constraints(
            conn, 1, "2026-08-11", "19:00", 13, 60, is_admin=False
        )
        assert ok is False
        assert "1 and 12" in msg

    def test_admin_party_size_above_30_is_invalid(self):
        conn = FakeConnection()
        ok, msg = validate_reservation_constraints(
            conn, 1, "2026-08-11", "19:00", 31, 60, is_admin=True
        )
        assert ok is False
        assert "1 and 30" in msg

    def test_admin_party_size_30_is_valid(self):
        conn = FakeConnection()
        # Location hard block check -> not blocked
        conn.queue_results([(0,)])
        # SELECT max_guests_per_slot, max_reservations_per_slot -> (120, 30)
        conn.queue_results([(120, 30)])
        # calculate_location_occupancy -> (0, 0)
        conn.queue_results([(0, 0)])
        ok, msg = validate_reservation_constraints(
            conn, 1, "2026-08-11", "19:00", 30, 60, is_admin=True
        )
        assert ok is True

    def test_location_hard_block_rejects(self):
        conn = FakeConnection()
        conn.queue_results([(1,)])  # check_location_blocks -> blocked
        ok, msg = validate_reservation_constraints(
            conn, 1, "2026-08-11", "19:00", 2, 60
        )
        assert ok is False
        assert "location block" in msg

    def test_guest_limit_exceeded(self):
        conn = FakeConnection()
        conn.queue_results([(0,)])  # not blocked
        conn.queue_results([(120, 30)])  # limits
        conn.queue_results([(119, 0)])  # 119 already in slot; +2 -> 121 > 120
        ok, msg = validate_reservation_constraints(
            conn, 1, "2026-08-11", "19:00", 2, 60
        )
        assert ok is False
        assert "maximum location capacity" in msg

    def test_reservation_limit_exceeded(self):
        conn = FakeConnection()
        conn.queue_results([(0,)])  # not blocked
        conn.queue_results([(120, 30)])  # limits
        conn.queue_results([(0, 30)])  # already 30 res; +1 -> 31 > 30
        ok, msg = validate_reservation_constraints(
            conn, 1, "2026-08-11", "19:00", 2, 60
        )
        assert ok is False
        assert "maximum of 30 reservations" in msg

    def test_invalid_location(self):
        conn = FakeConnection()
        conn.queue_results([(0,)])  # not blocked
        conn.queue_results([None])  # location lookup -> None
        ok, msg = validate_reservation_constraints(
            conn, 999, "2026-08-11", "19:00", 2, 60
        )
        assert ok is False
        assert "Invalid location" in msg