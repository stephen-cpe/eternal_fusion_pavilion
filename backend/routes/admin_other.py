from flask import Blueprint, jsonify, request, session
from models import Location, Room, Reservation, Customer, AuditLog
from database import db, get_connection, release_connection # Keep connection pool for utils
from datetime import datetime, timedelta, date as date_type # Import date separately to avoid conflict
from sqlalchemy import func, cast, Time, Date, Interval, select
from sqlalchemy.orm import joinedload
import json

# Keep using utils for complex calculations for now
from utils.time_utils import generate_time_slots

bp = Blueprint('admin_other', __name__)

@bp.route('/dashboard/stats', methods=['GET'])
def get_dashboard_stats():
    """Get dashboard statistics using ORM for basic info, keep utils for complex calcs."""
    if 'admin_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    location_id = request.args.get('location_id')
    date_str = request.args.get('date')

    if not location_id or not date_str:
        return jsonify({'error': 'location_id and date parameters are required'}), 400

    conn = None # For utils
    try:
        # This is the correct date object representing the requested date
        date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()

        # Get location info using ORM
        location = db.session.get(Location, location_id)
        if not location:
            return jsonify({'error': 'Location not found'}), 404

        # Get all reservations for the date using ORM
        reservations = db.session.query(Reservation).options(
            joinedload(Reservation.customer),
            joinedload(Reservation.room)
        ).filter(
            Reservation.location_id == location_id,
            Reservation.date == date_obj
        ).order_by(Reservation.time).all()

        # Get all rooms for this location using ORM
        rooms = db.session.query(Room).filter_by(location_id=location_id).order_by(Room.code).all()

        # Generate time slots (from utils)
        time_slots = generate_time_slots(date_obj)

        # --- Calculate room heatmap (using raw reservations data) ---
        room_heatmap = {}
        for room in rooms:
            room_heatmap[room.id] = {
                'id': room.id,
                'code': room.code,
                'name': room.name,
                'max_capacity': room.max_capacity,
                'is_active': room.is_active,
                'slots': {}
            }

        for slot in time_slots:
             slot_dt = datetime.strptime(slot, '%H:%M').time()
             # Calculate end time for overlap check
             slot_end_dt_naive = datetime.combine(date_obj, slot_dt) + timedelta(minutes=60)
             slot_end_time = slot_end_dt_naive.time() # This will only work correctly if duration doesn't cross midnight

             for room_id in room_heatmap:
                 occupancy = 0
                 reservation_count = 0
                 for res in reservations:
                     if res.room_id != room_id or res.status != 'confirmed':
                         continue
                     # Combine the reservation's date with its time for proper comparison
                     res_start_dt = datetime.combine(date_obj, res.time)
                     res_end_dt = res_start_dt + timedelta(minutes=res.duration_minutes)

                     # Combine the slot's date and time for comparison
                     slot_start_dt = datetime.combine(date_obj, slot_dt)
                     # slot_end_dt_naive calculated above is essentially slot_end_dt

                     # Check overlap: (res.start < slot.end) and (res.end > slot.start)
                     if res_start_dt < slot_end_dt_naive and res_end_dt > slot_start_dt:
                         occupancy += res.party_size
                         reservation_count += 1

                 max_cap = room_heatmap[room_id]['max_capacity']
                 room_heatmap[room_id]['slots'][slot] = {
                     'occupancy': occupancy,
                     'reservation_count': reservation_count,
                     'percentage': round((occupancy / max_cap) * 100, 1) if max_cap > 0 else 0
                 }
        # --- End heatmap calculation ---

        # --- Calculate location-wide stats per slot (using raw reservations data) ---
        location_stats = {}
        max_guests = location.max_guests_per_slot
        max_reservations = location.max_reservations_per_slot

        for slot in time_slots:
            slot_dt = datetime.strptime(slot, '%H:%M').time()
            slot_end_dt_naive = datetime.combine(date_obj, slot_dt) + timedelta(minutes=60)
            slot_end_time = slot_end_dt_naive.time() # Again, watch out for midnight crossing

            total_guests_in_slot = 0
            total_reservations_in_slot = 0

            # Combine slot date and time
            slot_start_dt = datetime.combine(date_obj, slot_dt)

            for res in reservations:
                if res.status != 'confirmed':
                    continue

                # Combine reservation date and time
                res_start_dt = datetime.combine(date_obj, res.time)
                res_end_dt = res_start_dt + timedelta(minutes=res.duration_minutes)

                # Check overlap
                if res_start_dt < slot_end_dt_naive and res_end_dt > slot_start_dt:
                    total_guests_in_slot += res.party_size
                    total_reservations_in_slot += 1

            location_stats[slot] = {
                'total_guests': total_guests_in_slot,
                'total_reservations': total_reservations_in_slot,
                'guests_percentage': round((total_guests_in_slot / max_guests) * 100, 1) if max_guests > 0 else 0,
                'reservations_percentage': round((total_reservations_in_slot / max_reservations) * 100, 1) if max_reservations > 0 else 0
            }
        # --- End location stats calculation ---

        # Format reservations for response using model's to_dict
        formatted_reservations = [res.to_dict() for res in reservations]

        return jsonify({
            'location': location.to_dict(), # Use model's to_dict
            'date': date_str,
            'time_slots': time_slots,
            'room_heatmap': list(room_heatmap.values()),
            'location_stats': location_stats,
            'reservations': formatted_reservations
        })

    except ValueError as ve:
         # Handle potential strptime errors more gracefully
         if 'date format' in str(ve):
             return jsonify({'error': f'Invalid date format: {ve}. Use YYYY-MM-DD'}), 400
         else:
             print(f"Value error getting dashboard stats: {ve}")
             return jsonify({'error': 'Invalid data encountered'}), 400
    except Exception as e:
        print(f"Error getting dashboard stats: {e}")
        import traceback
        traceback.print_exc() # Print full traceback for debugging
        return jsonify({'error': 'An internal error occurred'}), 500
    finally:
        if conn: release_connection(conn) # Ensure connection is released if used by utils


@bp.route('/rooms', methods=['GET'])
def get_rooms():
    """Get all rooms for a location using ORM."""
    if 'admin_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    location_id = request.args.get('location_id')
    if not location_id:
        return jsonify({'error': 'location_id parameter is required'}), 400

    try:
        # Attempt to convert location_id to integer
        try:
            loc_id_int = int(location_id)
        except ValueError:
            return jsonify({'error': 'Invalid location_id format'}), 400

        rooms = db.session.query(Room).filter_by(location_id=loc_id_int).order_by(Room.code).all()
        result = [room.to_dict() for room in rooms] # Use model's to_dict
        return jsonify(result)
    except Exception as e:
        print(f"Error fetching rooms: {e}")
        return jsonify({'error': 'An internal error occurred'}), 500


@bp.route('/audit-log', methods=['GET'])
def get_audit_log():
    """Get audit log entries using ORM."""
    if 'admin_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    try:
        limit = int(request.args.get('limit', 50))
    except ValueError:
        limit = 50 # Default if limit is invalid

    try:
        logs = db.session.query(AuditLog).options(
            joinedload(AuditLog.admin) # Eager load admin info
        ).order_by(AuditLog.created_at.desc()).limit(limit).all()

        result = [log.to_dict() for log in logs] # Use model's to_dict
        return jsonify(result)
    except Exception as e:
        print(f"Error fetching audit log: {e}")
        return jsonify({'error': 'An internal error occurred'}), 500

