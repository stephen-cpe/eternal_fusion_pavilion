"""
Dashboard statistics helpers extracted from routes/admin_other.py.

These compute the per-room heatmap and the location-wide per-slot stats from a
list of ORM Reservation rows. Both honor the same overlap rule as the booking
engine: a reservation overlaps a slot when
    res.start < slot.end AND res.end > slot.start.
Only 'confirmed' reservations contribute to occupancy or counts.
"""
from datetime import datetime, timedelta
from typing import Dict, List


def _overlap(res_start: datetime, res_end: datetime, slot_start: datetime, slot_end: datetime) -> bool:
    """True when [res_start, res_end) overlaps [slot_start, slot_end)."""
    return res_start < slot_end and res_end > slot_start


def calculate_room_heatmap(rooms, reservations, time_slots, date_obj, slot_duration_minutes=60):
    """Build the per-room, per-slot heatmap structure.

    Returns a list (one entry per room) with shape:
        {id, code, name, max_capacity, is_active, slots: {slot: {occupancy, reservation_count, percentage}}}
    """
    heatmap = {
        room.id: {
            "id": room.id,
            "code": room.code,
            "name": room.name,
            "max_capacity": room.max_capacity,
            "is_active": room.is_active,
            "slots": {},
        }
        for room in rooms
    }

    for slot in time_slots:
        slot_dt = datetime.strptime(slot, "%H:%M").time()
        slot_start = datetime.combine(date_obj, slot_dt)
        slot_end = slot_start + timedelta(minutes=slot_duration_minutes)

        for room_id, entry in heatmap.items():
            occupancy = 0
            reservation_count = 0
            for res in reservations:
                if res.room_id != room_id or res.status != "confirmed":
                    continue
                res_start = datetime.combine(date_obj, res.time)
                res_end = res_start + timedelta(minutes=res.duration_minutes)
                if _overlap(res_start, res_end, slot_start, slot_end):
                    occupancy += res.party_size
                    reservation_count += 1

            max_cap = entry["max_capacity"]
            entry["slots"][slot] = {
                "occupancy": occupancy,
                "reservation_count": reservation_count,
                "percentage": round((occupancy / max_cap) * 100, 1) if max_cap > 0 else 0,
            }

    return list(heatmap.values())


def calculate_location_stats(reservations, time_slots, date_obj, max_guests, max_reservations,
                              slot_duration_minutes=60) -> Dict[str, Dict]:
    """Build the per-slot location-wide stats structure.

    Returns a dict keyed by slot string with shape:
        {slot: {total_guests, total_reservations, guests_percentage, reservations_percentage}}
    """
    stats = {}
    for slot in time_slots:
        slot_dt = datetime.strptime(slot, "%H:%M").time()
        slot_start = datetime.combine(date_obj, slot_dt)
        slot_end = slot_start + timedelta(minutes=slot_duration_minutes)

        total_guests = 0
        total_reservations = 0
        for res in reservations:
            if res.status != "confirmed":
                continue
            res_start = datetime.combine(date_obj, res.time)
            res_end = res_start + timedelta(minutes=res.duration_minutes)
            if _overlap(res_start, res_end, slot_start, slot_end):
                total_guests += res.party_size
                total_reservations += 1

        stats[slot] = {
            "total_guests": total_guests,
            "total_reservations": total_reservations,
            "guests_percentage": round((total_guests / max_guests) * 100, 1) if max_guests > 0 else 0,
            "reservations_percentage": round((total_reservations / max_reservations) * 100, 1) if max_reservations > 0 else 0,
        }
    return stats