from flask import Blueprint, jsonify, request, session
from models import Admin
from database import db
import bcrypt

bp = Blueprint('admin_profile', __name__)

@bp.route('/profile', methods=['GET'])
def get_profile():
    if 'admin_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    admin_id = session['admin_id']
    try:

        admin = db.session.get(Admin, admin_id) # Use get for primary key lookup
        if admin:
            return jsonify({
                'username': admin.username,
                'fullName': admin.full_name,
                'role': admin.role
            })
        return jsonify({'error': 'Admin not found'}), 404
    except Exception as e:
        db.session.rollback()
        print(f"Error getting profile: {e}")
        return jsonify({'error': 'An internal error occurred'}), 500

@bp.route('/profile/name', methods=['PUT'])
def update_profile_name():
    if 'admin_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    data = request.json
    new_name = data.get('fullName', '').strip()

    if not new_name:
        return jsonify({'error': 'Full name is required'}), 400

    admin_id = session['admin_id']
    try:
        admin = db.session.get(Admin, admin_id)
        if not admin:
            return jsonify({'error': 'Admin not found'}), 404

        admin.full_name = new_name
        db.session.commit()

        # Update the name in the session as well
        session['admin_name'] = new_name
        return jsonify({'message': 'Name updated successfully'})
    except Exception as e:
        db.session.rollback()
        print(f"Error updating profile name: {e}")
        return jsonify({'error': 'An internal error occurred'}), 500

@bp.route('/profile/password', methods=['PUT'])
def update_profile_password():
    if 'admin_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    data = request.json
    current_password = data.get('currentPassword')
    new_password = data.get('newPassword')
    confirm_password = data.get('confirmPassword')

    if not all([current_password, new_password, confirm_password]):
        return jsonify({'error': 'All password fields are required'}), 400

    if new_password != confirm_password:
        return jsonify({'error': 'New passwords do not match'}), 400

    admin_id = session['admin_id']
    try:
        admin = db.session.get(Admin, admin_id)
        if not admin:
            return jsonify({'error': 'Admin not found'}), 404

        # Verify current password
        if not bcrypt.checkpw(current_password.encode('utf-8'), admin.password_hash.encode('utf-8')):
            return jsonify({'error': 'Incorrect current password'}), 400

        # Hash the new password and update
        new_salt = bcrypt.gensalt()
        new_hashed_password = bcrypt.hashpw(new_password.encode('utf-8'), new_salt).decode('utf-8')
        admin.password_hash = new_hashed_password

        db.session.commit()
        return jsonify({'message': 'Password updated successfully'})

    except Exception as e:
        db.session.rollback()
        print(f"Error updating profile password: {e}")
        return jsonify({'error': 'An internal error occurred'}), 500
