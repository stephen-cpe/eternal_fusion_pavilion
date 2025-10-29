from flask import Blueprint, jsonify, request, session
from models import ReservationBlock, AuditLog 
from database import db 
import json
from sqlalchemy.orm import joinedload # To eager load relationships

bp = Blueprint('admin_blocks', __name__)

def log_audit(admin_id, action, entity_type, entity_id, details):
    """Helper function to log actions."""
    try:
        log_entry = AuditLog(
            admin_id=admin_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            details=details
        )
        db.session.add(log_entry)
        # Commit happens in the main route
    except Exception as e:
        print(f"Error logging audit trail: {e}")

@bp.route('/blocks', methods=['GET'])
def get_blocks():
    """Get all reservation blocks using ORM."""
    if 'admin_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    location_id = request.args.get('location_id')

    try:
        query = db.session.query(ReservationBlock).options(
            joinedload(ReservationBlock.location),
            joinedload(ReservationBlock.room),
            joinedload(ReservationBlock.creator)
        )

        if location_id:
            query = query.filter(ReservationBlock.location_id == location_id)

        query = query.order_by(ReservationBlock.start_date.desc(), ReservationBlock.start_time.desc())
        blocks = query.all()

        result = [block.to_dict() for block in blocks] # Use model's to_dict
        return jsonify(result)

    except Exception as e:
        print(f"Error fetching blocks: {e}")
        return jsonify({'error': 'An internal error occurred'}), 500

@bp.route('/blocks', methods=['POST'])
def create_block():
    """Create a new reservation block using ORM."""
    if 'admin_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    data = request.json
    required_fields = ['location_id', 'start_date', 'end_date', 'start_time', 'end_time', 'block_type']
    if not all(field in data for field in required_fields):
         return jsonify({'error': f'Missing required fields: {", ".join(required_fields)}'}), 400

    if data['block_type'] not in ['hard', 'soft']:
        return jsonify({'error': 'block_type must be either "hard" or "soft"'}), 400

    room_id_value = data.get('room_id')
    if room_id_value == "":
        room_id_value = None  # Correctly handle empty string for NULL

    try:
        new_block = ReservationBlock(
            location_id=data['location_id'],
            room_id=room_id_value,
            start_date=data['start_date'],
            end_date=data['end_date'],
            start_time=data['start_time'],
            end_time=data['end_time'],
            block_type=data['block_type'],
            reason=data.get('reason', ''),
            created_by=session['admin_id']
        )
        db.session.add(new_block)
        db.session.flush() # Get the new block ID for logging

        # Log block creation
        log_audit(
            admin_id=session['admin_id'],
            action='create_block',
            entity_type='reservation_block',
            entity_id=new_block.id,
            details={"block_type": data["block_type"], "room_id": room_id_value}
        )

        db.session.commit()
        return jsonify({'id': new_block.id, 'message': 'Block created successfully'}), 201

    except Exception as e:
        db.session.rollback()
        print(f"Error creating block: {e}")
        # Provide more specific error if possible (e.g., integrity error)
        return jsonify({'error': 'An internal error occurred while creating the block'}), 500

@bp.route('/blocks/<int:block_id>', methods=['DELETE'])
def delete_block(block_id):
    """Delete a reservation block using ORM."""
    if 'admin_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    try:
        block = db.session.get(ReservationBlock, block_id)
        if not block:
            return jsonify({'error': 'Block not found'}), 404

        db.session.delete(block)

        # Log deletion
        log_audit(
            admin_id=session['admin_id'],
            action='delete_block',
            entity_type='reservation_block',
            entity_id=block_id,
            details={}
        )

        db.session.commit()
        return jsonify({'message': 'Block deleted successfully'})

    except Exception as e:
        db.session.rollback()
        print(f"Error deleting block: {e}")
        return jsonify({'error': 'An internal error occurred'}), 500
