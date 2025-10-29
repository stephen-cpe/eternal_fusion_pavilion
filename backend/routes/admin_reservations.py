from flask import Blueprint, jsonify, request, session
from models import Reservation, Customer, Location, Room, AuditLog
from database import db, get_connection, release_connection
from datetime import datetime, time, date, timedelta
import json
from sqlalchemy import or_, func, cast, Time, Date, Interval # For ORM querying
from sqlalchemy.orm import joinedload # To eager load relationships

# Keep using utils, which still use psycopg2 connection pool for now
from utils.room_assignment import (
    weighted_random_room_selection,
    generate_reservation_number,
    validate_reservation_constraints,
    check_room_blocks,
    calculate_room_occupancy
)

bp = Blueprint('admin_reservations', __name__)

def log_audit(admin_id, action, entity_type, entity_id, details):
    """Helper function to log actions."""
    try:
        log_entry = AuditLog(
            admin_id=admin_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            details=details # SQLAlchemy handles JSON conversion if type is JSON
        )
        db.session.add(log_entry)
        # Note: commit should happen within the route's try block
    except Exception as e:
        print(f"Error logging audit trail: {e}")
        # Decide if this should cause the main operation to fail (rollback)

@bp.route('/reservations', methods=['GET'])
def get_reservations():
    """Get all reservations with optional filtering using ORM."""
    if 'admin_id' not in session:
         return jsonify({'error': 'Unauthorized'}), 401

    location_id = request.args.get('location_id')
    date_str = request.args.get('date')
    search = request.args.get('search', '').strip()

    try:
        query = db.session.query(Reservation).options(
            joinedload(Reservation.customer),
            joinedload(Reservation.location),
            joinedload(Reservation.room)
        )

        if location_id:
             query = query.filter(Reservation.location_id == location_id)

        if date_str:
            try:
                filter_date = datetime.strptime(date_str, '%Y-%m-%d').date()
                query = query.filter(Reservation.date == filter_date)
            except ValueError:
                return jsonify({'error': 'Invalid date format. Use YYYY-MM-DD'}), 400

        if search:
            search_pattern = f"%{search}%"
            query = query.join(Reservation.customer).filter(
                or_(
                    Reservation.reservation_number.ilike(search_pattern),
                    Customer.name.ilike(search_pattern),
                     Customer.email.ilike(search_pattern)
                )
            )

        query = query.order_by(Reservation.date.desc(), Reservation.time.desc())
        reservations = query.all()

        result = [res.to_dict() for res in reservations] # Use to_dict method from model
        return jsonify(result)

    except Exception as e:
        print(f"Error fetching reservations: {e}")
        return jsonify({'error': 'An internal error occurred'}), 500


@bp.route('/reservations/<int:reservation_id>/status', methods=['PUT'])
def update_reservation_status(reservation_id):
    """Updates only the status of a reservation using ORM."""
    if 'admin_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    data = request.json
    status = data.get('status', '').strip()

    valid_statuses = ['confirmed', 'cancelled', 'no-show', 'completed']
    if not status or status not in valid_statuses:
         return jsonify({'error': f'Valid status is required ({", ".join(valid_statuses)})'}), 400

    try:
        reservation = db.session.get(Reservation, reservation_id)
        if not reservation:
            return jsonify({'error': 'Reservation not found'}), 404

        reservation.status = status
        reservation.updated_at = datetime.now() # Let ORM handle timezone if configured

        log_audit(
            admin_id=session['admin_id'],
             action='update_status',
            entity_type='reservation',
            entity_id=reservation_id,
            details={"new_status": status}
        )

        db.session.commit()
        return jsonify({'message': 'Reservation status updated successfully'})
    except Exception as e:
        db.session.rollback()
        print(f"Error updating reservation status: {e}")
        return jsonify({'error': 'An internal error occurred'}), 500


@bp.route('/reservations/<int:reservation_id>/details', methods=['PUT'])
def update_reservation_details(reservation_id):
    """Update full details of an existing reservation using ORM and existing utils."""
    if 'admin_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    data = request.json
    # Basic validation (add more as needed)
    required_fields = ['location_id', 'date', 'time', 'party_size', 'customer_name', 'customer_email', 'status']
    if not all(field in data for field in required_fields):
         return jsonify({'error': 'Missing required fields for update'}), 400

    conn = None 
    try:

        reservation = db.session.query(Reservation).options(
            joinedload(Reservation.customer) # Load customer to avoid extra query
        ).get(reservation_id)

        if not reservation:
             return jsonify({'error': 'Reservation not found'}), 404

        location_id = int(data['location_id'])
        date_str = data['date']
        time_str = data['time']
        party_size = int(data['party_size'])
        duration_minutes = int(data.get('duration_minutes', 60))
        room_id_input = data.get('room_id') # Can be None or empty string

        customer_name = data['customer_name']
        customer_email = data['customer_email']
        customer_phone = data.get('customer_phone')
        special_requests = data.get('special_requests')
        status = data['status']


        conn = get_connection()

        is_valid, error_msg = validate_reservation_constraints(
            conn, location_id, date_str, time_str, party_size, duration_minutes,
            exclude_id=reservation_id, is_admin=True
        )
        
        if not is_valid:
            release_connection(conn)
            return jsonify({'error': error_msg}), 400

        final_room_id = None
        manual_room_assignment = False
        soft_block_override = False

        if room_id_input and str(room_id_input).isdigit():
            # Admin manually selected a room
            room_id = int(room_id_input)
            manual_room_assignment = True
            
            # Check for hard blocks
            if check_room_blocks(conn, room_id, date_str, time_str, duration_minutes, 'hard'):
                release_connection(conn)
                return jsonify({'error': 'Selected room is blocked (hard block) for this time'}), 400

            soft_block_override = check_room_blocks(conn, room_id, date_str, time_str, duration_minutes, 'soft')
            if soft_block_override and session.get('admin_role') != 'manager':
                release_connection(conn)
                return jsonify({
                    'error': 'This room is soft-blocked. Only managers can override.'
                }), 403

            # Validate room capacity (excluding self)
            current_occupancy = calculate_room_occupancy(
                conn, room_id, date_str, time_str, duration_minutes,
                exclude_id=reservation_id
             )
            room = db.session.get(Room, room_id) # Fetch room using ORM
            if not room:
                 release_connection(conn)
                 return jsonify({'error': 'Selected room not found'}), 404

            if current_occupancy + party_size > room.max_capacity:
                 release_connection(conn)
                 return jsonify({'error': f'Selected room ({room.name}) exceeds capacity ({room.max_capacity}) with {party_size} guests (currently {current_occupancy})'}), 400

            final_room_id = room_id
        else:
            # Auto-assign room using utility
            selected_room = weighted_random_room_selection(
                conn, location_id, date_str, time_str, party_size, duration_minutes,
                exclude_id=reservation_id
            )
            if not selected_room:
                 release_connection(conn)
                 return jsonify({'error': 'No suitable rooms available for this time slot'}), 400
            final_room_id = selected_room['id']
            
            soft_block_override = check_room_blocks(conn, final_room_id, date_str, time_str, duration_minutes, 'soft')
            if soft_block_override and session.get('admin_role') != 'manager':
                release_connection(conn)
                return jsonify({
                    'error': 'Auto-assignment failed. The only available room is soft-blocked and requires manager override.'
                }), 403

        release_connection(conn) # Release connection after utils are done

        
        customer = db.session.query(Customer).filter_by(email=customer_email).first()
        if customer:
            # Update existing customer
            customer.name = customer_name
            customer.phone = customer_phone
            customer.updated_at = datetime.now()
        else:
            # Create new customer
            customer = Customer(
                name=customer_name,
                email=customer_email,
                phone=customer_phone
            )
            db.session.add(customer)
            db.session.flush() # To get the new customer ID if needed immediately

        # Ensure customer_id is set for the reservation
        customer_id = customer.id

        reservation.customer_id = customer_id
        reservation.location_id = location_id
        reservation.room_id = final_room_id
        reservation.date = datetime.strptime(date_str, '%Y-%m-%d').date()
        reservation.time = datetime.strptime(time_str, '%H:%M').time()
        reservation.duration_minutes = duration_minutes
        reservation.party_size = party_size
        reservation.status = status
        reservation.special_requests = special_requests
        reservation.updated_at = datetime.now()

        audit_details = {
            "source": "admin_update",
            "updated_data": data,
            "final_room_id": final_room_id,
            "manual_room_assignment": manual_room_assignment,
            "soft_block_override": soft_block_override
        }
        log_audit(
            admin_id=session['admin_id'],
            action='update_details',
             entity_type='reservation',
            entity_id=reservation_id,
            details=audit_details
        )

        db.session.commit()
        return jsonify({'message': 'Reservation updated successfully'})

    except ValueError as ve:
         if conn: release_connection(conn)
         db.session.rollback()
         print(f"Value error updating reservation details: {ve}")
         return jsonify({'error': f'Invalid input format: {ve}'}), 400
    except Exception as e:
        if conn: release_connection(conn)
        db.session.rollback()
        print(f"Error updating reservation details: {e}")
        return jsonify({'error': 'An internal error occurred'}), 500


@bp.route('/reservations/<int:reservation_id>', methods=['DELETE'])
def delete_reservation(reservation_id):
    if 'admin_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    try:
        reservation = db.session.get(Reservation, reservation_id)
        if not reservation:
            return jsonify({'error': 'Reservation not found'}), 404

        db.session.delete(reservation)

        log_audit(
            admin_id=session['admin_id'],
            action='delete_reservation',
            entity_type='reservation',
            entity_id=reservation_id,
             details={} # No extra details needed for delete usually
        )

        db.session.commit()
        return jsonify({'message': 'Reservation deleted successfully'})
    except Exception as e:
        db.session.rollback()
        print(f"Error deleting reservation: {e}")
        return jsonify({'error': 'An internal error occurred'}), 500


@bp.route('/reservations/<int:reservation_id>/room', methods=['PUT'])
def update_reservation_room(reservation_id):
    """Manually override room assignment using ORM and utils."""
    if 'admin_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    data = request.json
    new_room_id = data.get('room_id')

    if not new_room_id or not str(new_room_id).isdigit():
        return jsonify({'error': 'Valid room_id is required'}), 400
    new_room_id = int(new_room_id)

    conn = None # For utils
    try:
        reservation = db.session.get(Reservation, reservation_id)
        if not reservation:
             return jsonify({'error': 'Reservation not found'}), 404

        old_room_id = reservation.room_id
        # Extract necessary details for validation utils
        date_str = reservation.date.isoformat()
        time_str = reservation.time.strftime('%H:%M')
        duration_minutes = reservation.duration_minutes
        party_size = reservation.party_size

        new_room = db.session.get(Room, new_room_id)
        if not new_room:
             return jsonify({'error': 'Target room not found'}), 404
        if new_room.location_id != reservation.location_id:
             return jsonify({'error': 'Cannot move reservation to a room in a different location'}), 400


        conn = get_connection()

        if check_room_blocks(conn, new_room_id, date_str, time_str, duration_minutes, 'hard'):
            release_connection(conn)
            return jsonify({'error': 'Selected room is blocked (hard block) for this time'}), 400

        exclude_id_for_calc = reservation_id if old_room_id == new_room_id else None
        current_occupancy = calculate_room_occupancy(
            conn, new_room_id, date_str, time_str, duration_minutes, exclude_id_for_calc
        )
        if current_occupancy + party_size > new_room.max_capacity:
             release_connection(conn)
             return jsonify({
                 'error': f'Room ({new_room.name}) does not have enough capacity. Current: {current_occupancy}, Needed: {party_size}, Max: {new_room.max_capacity}'
             }), 400

        soft_block_override = check_room_blocks(
            conn, new_room_id, date_str, time_str, duration_minutes, 'soft'
        )
        
        if soft_block_override and session.get('admin_role') != 'manager':
            release_connection(conn) # Release connection before returning
            return jsonify({
                'error': 'This room is soft-blocked. Only managers can override.'
            }), 403

        release_connection(conn)

        reservation.room_id = new_room_id
        reservation.updated_at = datetime.now()

        audit_details = {
            "old_room_id": old_room_id,
            "new_room_id": new_room_id,
            "soft_block_override": soft_block_override
        }
        log_audit(
            admin_id=session['admin_id'],
            action='manual_room_override',
            entity_type='reservation',
            entity_id=reservation_id,
            details=audit_details
        )

        db.session.commit()
        return jsonify({'message': 'Room assignment updated successfully'})

    except Exception as e:
        if conn: release_connection(conn)
        db.session.rollback()
        print(f"Error updating reservation room: {e}")
        return jsonify({'error': 'An internal error occurred'}), 500


@bp.route('/reservations/create', methods=['POST'])
def create_admin_reservation():
    """Create a new reservation with admin privileges using ORM and utils."""
    if 'admin_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    data = request.json
    required_fields = ['location_id', 'date', 'time', 'party_size', 'customer_name', 'customer_email']
    if not all(field in data for field in required_fields):
         return jsonify({'error': f'Missing required fields: {", ".join(required_fields)}'}), 400

    conn = None # For utils
    try:
        location_id = int(data['location_id'])
        party_size = int(data['party_size'])
        duration_minutes = int(data.get('duration_minutes', 60))
        date_str = data['date']
        time_str = data['time']
        room_id_input = data.get('room_id') # Optional manual assignment

        if not 1 <= party_size <= 30:
            return jsonify({'error': 'Party size must be between 1 and 30 for admin bookings.'}), 400

        conn = get_connection()

        is_valid, error_msg = validate_reservation_constraints(
            conn, location_id, date_str, time_str, party_size, duration_minutes, is_admin=True
        )
        # ------------------------------------
        if not is_valid:
             release_connection(conn)
             return jsonify({'error': error_msg}), 400

        # Select room (or use manual assignment if provided)
        final_room_id = None
        soft_block_override = False
        manual_room_assignment = False

        if room_id_input and str(room_id_input).isdigit():
            manual_room_assignment = True
            room_id = int(room_id_input)
            # Validate hard blocks
            if check_room_blocks(conn, room_id, date_str, time_str, duration_minutes, 'hard'):
                 release_connection(conn)
                 return jsonify({'error': 'Selected room is blocked (hard block) for this time'}), 400
             # Check soft block
            soft_block_override = check_room_blocks(conn, room_id, date_str, time_str, duration_minutes, 'soft')

            if soft_block_override and session.get('admin_role') != 'manager':
                release_connection(conn) # Release connection before returning
                return jsonify({
                    'error': 'This room is soft-blocked. Only managers can override.'
                }), 403

            # Validate room capacity using utils
            current_occupancy = calculate_room_occupancy(
                conn, room_id, date_str, time_str, duration_minutes
            )
            # Fetch room using ORM to check max capacity
            room = db.session.get(Room, room_id)
            if not room:
                 release_connection(conn)
                 return jsonify({'error': 'Selected room not found'}), 404

            if current_occupancy + party_size > room.max_capacity:
                 release_connection(conn)
                 return jsonify({'error': f'Selected room ({room.name}) exceeds capacity ({room.max_capacity}) with {party_size} guests (currently {current_occupancy})'}), 400

            final_room_id = room_id
        else:
             # Use weighted-random algorithm (utils)
            selected_room = weighted_random_room_selection(
                conn, location_id, date_str, time_str, party_size, duration_minutes
            )
            if not selected_room:
                 release_connection(conn)
                 return jsonify({'error': 'No rooms available for this time slot'}), 400
            final_room_id = selected_room['id']
            # Check if auto-assigned room overrides a soft block
            soft_block_override = check_room_blocks(conn, final_room_id, date_str, time_str, duration_minutes, 'soft')

            if soft_block_override and session.get('admin_role') != 'manager':
                release_connection(conn) # Release connection before returning
                return jsonify({
                    'error': 'Auto-assignment failed. The only available room is soft-blocked and requires manager override.'
                }), 403

        release_connection(conn) # Done with utils

        customer = db.session.query(Customer).filter_by(email=data['customer_email']).first()
        if customer:
            customer.name = data['customer_name']
            customer.phone = data.get('customer_phone')
            customer.updated_at = datetime.now()
        else:
            customer = Customer(
                 name=data['customer_name'],
                email=data['customer_email'],
                phone=data.get('customer_phone')
            )
            db.session.add(customer)
            db.session.flush() # Get ID

        customer_id = customer.id

        # Get location code for reservation number
        location = db.session.get(Location, location_id)
        if not location:
             # This rollback might be redundant if the commit doesn't happen, but good practice
             db.session.rollback()
             return jsonify({'error': 'Invalid location selected'}), 400
        location_code = location.code

         # Generate reservation number (utils)
        reservation_number = generate_reservation_number(location_code)

        # Create reservation object
        new_reservation = Reservation(
            reservation_number=reservation_number,
            customer_id=customer_id,
            location_id=location_id,
            room_id=final_room_id,
            date=datetime.strptime(date_str, '%Y-%m-%d').date(),
             time=datetime.strptime(time_str, '%H:%M').time(),
            duration_minutes=duration_minutes,
            party_size=party_size,
            status='confirmed', # Default for admin creation
            special_requests=data.get('special_requests', '')
        )
        db.session.add(new_reservation)
        db.session.flush() # Get the new reservation ID for logging

         # Log admin creation
        audit_details = {
            "source": "admin",
            "room_id": final_room_id,
            "manual_room_assignment": manual_room_assignment,
            "soft_block_override": soft_block_override
        }
        log_audit(
            admin_id=session['admin_id'],
             action='create_reservation',
            entity_type='reservation',
            entity_id=new_reservation.id,
            details=audit_details
        )

        db.session.commit()

        return jsonify({
            'id': new_reservation.id,
            'reservation_number': reservation_number,
             'message': 'Reservation created successfully'
        }), 201

    except ValueError as ve:
         # Ensure connection is released even on value errors
         if conn: release_connection(conn)
         db.session.rollback()
         print(f"Value error creating reservation: {ve}")
         return jsonify({'error': f'Invalid input format: {ve}'}), 400
    except Exception as e:
         # Ensure connection is released on general exceptions
        if conn: release_connection(conn)
        db.session.rollback()
        print(f"Error creating admin reservation: {e}")

        import traceback
        traceback.print_exc()
        # ----------------------------------------------------
        return jsonify({'error': 'An internal error occurred'}), 500
    # finally:
    #     if conn: release_connection(conn)
    # Removing finally block as release_connection is called within try/except