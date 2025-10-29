from flask import Blueprint, jsonify, request
import datetime
from models import Location, Reservation, Customer, Room
from database import db, get_connection, release_connection # Keep connection pool for utils

# Keep using utils, which still use psycopg2 connection pool
from utils.room_assignment import (
    weighted_random_room_selection,
    generate_reservation_number,
    validate_reservation_constraints
)
from utils.time_utils import generate_time_slots, is_valid_booking_time

bp = Blueprint('reservations', __name__)

@bp.route('/locations', methods=['GET'])
def get_locations():
    """Get all available locations using ORM."""
    try:
        locations = db.session.query(Location).order_by(Location.name).all()
        return jsonify({
            'locations': [loc.to_dict() for loc in locations] # Use model's to_dict
        })
    except Exception as e:
        print(f"Error fetching locations: {e}")
        return jsonify({'error': 'An internal error occurred'}), 500


@bp.route('/availability', methods=['GET'])
def availability():
    """Get availability using utils (which use psycopg2)."""
    location_id = request.args.get('location_id')
    date_str = request.args.get('date')

    if not location_id or not date_str:
        return jsonify({'error': 'location_id and date parameters are required'}), 400

    try:
        date_obj = datetime.datetime.strptime(date_str, '%Y-%m-%d').date()
        if date_obj < datetime.date.today():
            return jsonify({'error': 'Cannot check availability for past dates'}), 400
    except ValueError:
        return jsonify({'error': 'Invalid date format. Use YYYY-MM-DD'}), 400

    # Generate time slots for the date (from utils)
    slots = generate_time_slots(date_obj)

    conn = None
    try:
        conn = get_connection() # Get connection for utils
        slots_with_availability = []

        # Get location limits using ORM for efficiency before looping
        location = db.session.get(Location, location_id)
        if not location:
            release_connection(conn)
            return jsonify({'error': 'Location not found'}), 404
        max_guests = location.max_guests_per_slot
        max_reservations = location.max_reservations_per_slot

        for slot in slots:
            # Validate constraints for this slot using utils
            is_valid, _ = validate_reservation_constraints(
                conn, int(location_id), date_str, slot, 1, 60 # Check feasibility for 1 guest
            )

            # Get current occupancy (could potentially be optimized with ORM later)
            start_dt = datetime.datetime.strptime(slot, '%H:%M')
            end_dt = start_dt + datetime.timedelta(minutes=60)
            end_time = end_dt.strftime('%H:%M')

            # Use raw SQL within utils for this complex overlap check for now
            with conn.cursor() as cursor:
                 cursor.execute("""
                    SELECT
                        COALESCE(SUM(party_size), 0) as total_guests,
                        COUNT(*) as total_reservations
                    FROM reservations
                    WHERE location_id = %s
                    AND date = %s
                    AND status = 'confirmed'
                    AND time < %s::time
                    AND (time + (duration_minutes || ' minutes')::interval)::time > %s::time
                """, (location_id, date_str, end_time, slot))
                 result = cursor.fetchone()

            total_guests = result[0] if result else 0
            total_reservations = result[1] if result else 0

            slots_available = max_reservations - total_reservations
            guests_available = max_guests - total_guests

            slots_with_availability.append({
                'time': slot,
                'available': is_valid,
                'slotsLeft': max(0, slots_available),
                'guestsAvailable': max(0, guests_available)
            })

        return jsonify({
            'date': date_str,
            'slots': slots_with_availability
        })
    except Exception as e:
         print(f"Error checking availability: {e}")
         return jsonify({'error': 'An internal error occurred during availability check'}), 500
    finally:
        if conn:
            release_connection(conn)


@bp.route('/', methods=['POST'])
def create_reservation():
    """Create a new reservation using ORM and utils."""
    data = request.json
    required_fields = ['location_id', 'date', 'time', 'party_size', 'name', 'email']
    if not all(field in data for field in required_fields):
         return jsonify({'error': f'Missing required field: {", ".join(required_fields)}'}), 400

    # Basic Validations
    try:
        party_size = int(data['party_size'])
        if not 1 <= party_size <= 12:
            return jsonify({
                'error': 'Party size must be between 1 and 12. For larger parties, please call us.',
                'requiresCall': party_size > 12
            }), 400
    except (ValueError, TypeError):
        return jsonify({'error': 'Invalid party size'}), 400

    try:
        reservation_date = datetime.datetime.strptime(data['date'], '%Y-%m-%d').date()
        if reservation_date < datetime.date.today():
            return jsonify({'error': 'Cannot book reservations for past dates'}), 400
    except ValueError:
        return jsonify({'error': 'Invalid date format. Use YYYY-MM-DD'}), 400

    if not is_valid_booking_time(reservation_date, data['time']):
        return jsonify({'error': 'Selected time is outside dining hours'}), 400

    location_id = int(data['location_id'])
    duration_minutes = 60 # Default

    conn = None # For utils
    try:
        # --- Use utility functions (with psycopg2 connection) ---
        conn = get_connection()
        # Validate reservation constraints using utils
        is_valid, error_msg = validate_reservation_constraints(
            conn, location_id, data['date'], data['time'], party_size, duration_minutes
        )
        if not is_valid:
            release_connection(conn)
            return jsonify({'error': error_msg}), 400

        # Select room using weighted-random algorithm (utils)
        selected_room = weighted_random_room_selection(
            conn, location_id, data['date'], data['time'], party_size, duration_minutes
        )
        if not selected_room:
            release_connection(conn)
            return jsonify({'error': 'No rooms available for this time slot'}), 400

        release_connection(conn) # Done with utils
        # --- End utility usage ---

        # Get location code for reservation number using ORM
        location = db.session.get(Location, location_id)
        if not location:
            return jsonify({'error': 'Invalid location selected'}), 400
        location_code = location.code

        # Generate reservation number (utils)
        reservation_number = generate_reservation_number(location_code)

        # Find or create customer using ORM
        customer = db.session.query(Customer).filter_by(email=data['email']).first()
        if customer:
            customer.name = data['name']
            customer.phone = data.get('phone')
            customer.updated_at = datetime.datetime.now()
        else:
            customer = Customer(
                name=data['name'],
                email=data['email'],
                phone=data.get('phone'),
                newsletter_signup=False # Default for new reservation customer
            )
            db.session.add(customer)
            db.session.flush() # Get ID
        
        customer_id = customer.id

        # Create reservation object
        new_reservation = Reservation(
            reservation_number=reservation_number,
            customer_id=customer_id,
            location_id=location_id,
            room_id=selected_room['id'],
            date=reservation_date,
            time=datetime.datetime.strptime(data['time'], '%H:%M').time(),
            duration_minutes=duration_minutes,
            party_size=party_size,
            status='confirmed',
            special_requests=data.get('special_requests', '')
        )
        db.session.add(new_reservation)
        db.session.commit()

        return jsonify({
            'id': new_reservation.id,
            'reservationNumber': reservation_number,
            'message': f'Reservation confirmed! Your reservation number is {reservation_number}',
            'room': { # Provide room details back
                'code': selected_room['code'],
                'name': selected_room['name']
            }
        }), 201

    except ValueError as ve:
         if conn: release_connection(conn)
         db.session.rollback()
         print(f"Value error during reservation creation: {ve}")
         return jsonify({'error': f'Invalid input data format: {ve}'}), 400
    except Exception as e:
        if conn: release_connection(conn)
        db.session.rollback()
        print(f"Error creating reservation: {e}")
        return jsonify({'error': 'An internal server error occurred'}), 500
