from flask import Blueprint, jsonify, request, session
from models import Location, Room, Reservation, AuditLog
from database import db
from datetime import datetime
from sqlalchemy.orm import joinedload

from utils.time_utils import generate_time_slots
from utils.dashboard import calculate_room_heatmap, calculate_location_stats

bp = Blueprint('admin_other', __name__)

@bp.route('/dashboard/stats', methods=['GET'])
def get_dashboard_stats():
    """Get dashboard statistics for a given location and date."""
    if 'admin_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    location_id = request.args.get('location_id')
    date_str = request.args.get('date')

    if not location_id or not date_str:
        return jsonify({'error': 'location_id and date parameters are required'}), 400

    try:
        date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()

        location = db.session.get(Location, location_id)
        if not location:
            return jsonify({'error': 'Location not found'}), 404

        reservations = db.session.query(Reservation).options(
            joinedload(Reservation.customer),
            joinedload(Reservation.room)
        ).filter(
            Reservation.location_id == location_id,
            Reservation.date == date_obj
        ).order_by(Reservation.time).all()

        rooms = db.session.query(Room).filter_by(location_id=location_id).order_by(Room.code).all()

        time_slots = generate_time_slots(date_obj)

        room_heatmap = calculate_room_heatmap(rooms, reservations, time_slots, date_obj)
        location_stats = calculate_location_stats(
            reservations, time_slots, date_obj,
            location.max_guests_per_slot, location.max_reservations_per_slot,
        )

        return jsonify({
            'location': location.to_dict(),
            'date': date_str,
            'time_slots': time_slots,
            'room_heatmap': room_heatmap,
            'location_stats': location_stats,
            'reservations': [res.to_dict() for res in reservations],
        })

    except ValueError as ve:
        if 'date format' in str(ve):
            return jsonify({'error': f'Invalid date format: {ve}. Use YYYY-MM-DD'}), 400
        print(f"Value error getting dashboard stats: {ve}")
        return jsonify({'error': 'Invalid data encountered'}), 400
    except Exception as e:
        print(f"Error getting dashboard stats: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': 'An internal error occurred'}), 500


@bp.route('/rooms', methods=['GET'])
def get_rooms():
    """Get all rooms for a location using ORM."""
    if 'admin_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    location_id = request.args.get('location_id')
    if not location_id:
        return jsonify({'error': 'location_id parameter is required'}), 400

    try:
        loc_id_int = int(location_id)
    except ValueError:
        return jsonify({'error': 'Invalid location_id format'}), 400

    try:
        rooms = db.session.query(Room).filter_by(location_id=loc_id_int).order_by(Room.code).all()
        return jsonify([room.to_dict() for room in rooms])
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
        limit = 50

    try:
        logs = db.session.query(AuditLog).options(
            joinedload(AuditLog.admin)
        ).order_by(AuditLog.created_at.desc()).limit(limit).all()

        return jsonify([log.to_dict() for log in logs])
    except Exception as e:
        print(f"Error fetching audit log: {e}")
        return jsonify({'error': 'An internal error occurred'}), 500