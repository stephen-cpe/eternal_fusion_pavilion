"""
Room Assignment Algorithm
Implements weighted-random room selection based on capacity constraints
"""
import random
from typing import Optional, List, Dict, Tuple
from datetime import datetime, timedelta

def calculate_room_occupancy(
    conn,
    room_id: int,
    date: str,
    start_time: str,
    duration_minutes: int = 60,
    exclude_id: Optional[int] = None
) -> int:
    """
    Calculate current occupancy for a room during a time window.
    Returns total guests in the room during the overlapping period.
    Can optionally exclude a reservation ID from the count.
    """
    with conn.cursor() as cursor:
        # Calculate end time for the new reservation
        start_dt = datetime.strptime(start_time, '%H:%M')
        end_dt = start_dt + timedelta(minutes=duration_minutes)
        end_time = end_dt.strftime('%H:%M')

        query = """
            SELECT COALESCE(SUM(party_size), 0)
            FROM reservations
            WHERE room_id = %s
            AND date = %s
            AND status = 'confirmed'
            AND time < %s::time
            AND (time + (duration_minutes || ' minutes')::interval)::time > %s::time
        """
        params = [room_id, date, end_time, start_time]

        if exclude_id is not None:
            query += " AND id != %s"
            params.append(exclude_id)

        cursor.execute(query, tuple(params))
        result = cursor.fetchone()
        return result[0] if result else 0


def calculate_location_occupancy(
    conn,
    location_id: int,
    date: str,
    start_time: str,
    duration_minutes: int = 60,
    exclude_id: Optional[int] = None
) -> Tuple[int, int]:
    """
    Calculate current location-wide occupancy during a time window.
    Returns (total_guests, total_reservations) for the location.
    Can optionally exclude a reservation ID from the count.
    """
    with conn.cursor() as cursor:
        start_dt = datetime.strptime(start_time, '%H:%M')
        end_dt = start_dt + timedelta(minutes=duration_minutes)
        end_time = end_dt.strftime('%H:%M')

        query = """
            SELECT
                COALESCE(SUM(party_size), 0) as total_guests,
                COUNT(*) as total_reservations
            FROM reservations
            WHERE location_id = %s
            AND date = %s
            AND status = 'confirmed'
            AND time < %s::time
            AND (time + (duration_minutes || ' minutes')::interval)::time > %s::time
        """
        params = [location_id, date, end_time, start_time]

        if exclude_id is not None:
            query += " AND id != %s"
            params.append(exclude_id)

        cursor.execute(query, tuple(params))
        result = cursor.fetchone()
        return (result[0] if result else 0, result[1] if result else 0)


def check_room_blocks(
    conn,
    room_id: int,
    date: str,
    start_time: str,
    duration_minutes: int = 60,
    block_type: str = 'hard'
) -> bool:
    """
    Check if a room is blocked during the requested time.
    Returns True if blocked, False if available.
    Can check for 'hard' or 'soft' blocks.
    """
    with conn.cursor() as cursor:
        start_dt = datetime.strptime(start_time, '%H:%M')
        end_dt = start_dt + timedelta(minutes=duration_minutes)
        end_time = end_dt.strftime('%H:%M')

        # Check for blocks that overlap with this time
        cursor.execute("""
            SELECT COUNT(*)
            FROM reservation_blocks
            WHERE room_id = %s
            AND block_type = %s
            AND %s BETWEEN start_date AND end_date
            AND start_time < %s::time
            AND end_time > %s::time
        """, (room_id, block_type, date, end_time, start_time))

        result = cursor.fetchone()
        return result[0] > 0 if result else False


def check_location_blocks(
    conn,
    location_id: int,
    date: str,
    start_time: str,
    duration_minutes: int = 60
) -> bool:
    """
    Check if a location is blocked (hard block) during the requested time.
    Returns True if blocked, False if available.
    """
    with conn.cursor() as cursor:
        start_dt = datetime.strptime(start_time, '%H:%M')
        end_dt = start_dt + timedelta(minutes=duration_minutes)
        end_time = end_dt.strftime('%H:%M')

        # Check for location-wide hard blocks (room_id IS NULL)
        cursor.execute("""
            SELECT COUNT(*)
            FROM reservation_blocks
            WHERE location_id = %s
            AND room_id IS NULL
            AND block_type = 'hard'
            AND %s BETWEEN start_date AND end_date
            AND start_time < %s::time
            AND end_time > %s::time
        """, (location_id, date, end_time, start_time))

        result = cursor.fetchone()
        return result[0] > 0 if result else False


def get_candidate_rooms(
    conn,
    location_id: int,
    date: str,
    start_time: str,
    party_size: int,
    duration_minutes: int = 60,
    exclude_id: Optional[int] = None
) -> List[Dict]:
    """
    Get all candidate rooms that can accommodate the party.
    Returns list of rooms with their available capacity and weight.
    Weight is calculated based on available capacity (primary)
    and reservation count (tie-breaker), per the spec.
    """
    with conn.cursor() as cursor:
        # Get all active rooms for this location
        cursor.execute("""
            SELECT id, code, name, max_capacity
            FROM rooms
            WHERE location_id = %s
            AND is_active = true
        """, (location_id,))

        rooms = cursor.fetchall()
        candidates = []

        # Calculate end time for the slot check
        start_dt = datetime.strptime(start_time, '%H:%M')
        end_dt = start_dt + timedelta(minutes=duration_minutes)
        end_time = end_dt.strftime('%H:%M')

        for room in rooms:
            room_id, code, name, max_capacity = room

            # 1. Check if room is 'hard' blocked
            if check_room_blocks(conn, room_id, date, start_time, duration_minutes, 'hard'):
                continue

            # 2. Calculate current occupancy
            current_occupancy = calculate_room_occupancy(
                conn, room_id, date, start_time, duration_minutes, exclude_id
            )

            # 3. Calculate available capacity
            available_capacity = max_capacity - current_occupancy

            # 4. Check if room can accommodate the party
            if available_capacity >= party_size:

                # 5. Get reservation count for this slot (for tie-breaker)
                # This query is fixed to check the slot, not the whole day.
                cursor.execute("""
                    SELECT COUNT(*)
                    FROM reservations
                    WHERE room_id = %s
                    AND date = %s
                    AND status = 'confirmed'
                    AND time < %s::time
                    AND (time + (duration_minutes || ' minutes')::interval)::time > %s::time
                """, (room_id, date, end_time, start_time))

                reservation_count = cursor.fetchone()[0]

                # 6. Calculate weight per spec
                # This weight heavily prioritizes available capacity,
                # then uses (100 - reservation_count) as a tie-breaker.
                weight = (available_capacity * 1000) + (100 - reservation_count)

                candidates.append({
                    'id': room_id,
                    'code': code,
                    'name': name,
                    'max_capacity': max_capacity,
                    'current_occupancy': current_occupancy,
                    'available_capacity': available_capacity,
                    'reservation_count': reservation_count,
                    'weight': weight
                })

        return candidates


def weighted_random_room_selection(
    conn,
    location_id: int,
    date: str,
    start_time: str,
    party_size: int,
    duration_minutes: int = 60,
    exclude_id: Optional[int] = None
) -> Optional[Dict]:
    """
    Select a room using weighted-random algorithm.
    The weights are pre-calculated in get_candidate_rooms
    to include the capacity and tie-breaker rule.
    """
    candidates = get_candidate_rooms(
        conn, location_id, date, start_time, party_size, duration_minutes, exclude_id
    )

    if not candidates:
        return None

    # This logic is now simplified, as the sorting/tie-breaking
    # is baked into the 'weight' from get_candidate_rooms.
    weights = [c['weight'] for c in candidates]
    selected = random.choices(candidates, weights=weights, k=1)[0]

    return selected


def generate_reservation_number(location_code: str) -> str:
    """
    Generate a unique reservation number in format: LOC-XXXXX
    Example: JPN-A43C7
    """
    import string
    chars = string.ascii_uppercase + string.digits
    random_part = ''.join(random.choices(chars, k=5))
    return f"{location_code}-{random_part}"


def validate_reservation_constraints(
    conn,
    location_id: int,
    date: str,
    start_time: str,
    party_size: int,
    duration_minutes: int = 60,
    exclude_id: Optional[int] = None,
    is_admin: bool = False
) -> Tuple[bool, Optional[str]]:
    """
    Validate all reservation constraints for a location.
    Can optionally exclude a reservation ID from the count.
    Returns (is_valid, error_message).
    """
    if not is_admin and not 1 <= party_size <= 12:
        return False, "Party size must be between 1 and 12 for online bookings."
    elif is_admin and not 1 <= party_size <= 30: # Max room capacity
        return False, "Party size must be between 1 and 30 for admin bookings."

    # Check location-wide hard blocks
    if check_location_blocks(conn, location_id, date, start_time, duration_minutes):
        return False, "This time slot is not available for reservations due to a location block."

    # Get location limits
    with conn.cursor() as cursor:
        cursor.execute("""
            SELECT max_guests_per_slot, max_reservations_per_slot
            FROM locations
            WHERE id = %s
        """, (location_id,))

        result = cursor.fetchone()
        if not result:
            return False, "Invalid location."

        max_guests, max_reservations = result

    # Check current occupancy, excluding the reservation if provided
    total_guests, total_reservations = calculate_location_occupancy(
        conn, location_id, date, start_time, duration_minutes, exclude_id
    )

    # Validate guest limit
    if total_guests + party_size > max_guests:
        return False, f"This time slot would exceed the maximum location capacity of {max_guests} guests (currently {total_guests})."

    # Validate reservation limit
    if total_reservations + 1 > max_reservations:
        return False, f"This time slot has reached the maximum of {max_reservations} reservations (currently {total_reservations})."

    return True, None
