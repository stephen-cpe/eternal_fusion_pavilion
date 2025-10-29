from flask import Blueprint, jsonify, request, session
from models import Admin  # Use the SQLAlchemy model
from database import db   # Use the SQLAlchemy session
import bcrypt
import re

bp = Blueprint('admin_auth', __name__)

# Basic email validation (consider a more robust library if needed)
def is_valid_email(email):
    """Validate email format"""
    email_regex = r'^[^\s@]+@[^\s@]+\.[^\s@]+$'
    return re.match(email_regex, email) is not None

@bp.route('/login', methods=['POST'])
def login():
    data = request.json
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()

    print(f"Login attempt for username: {username}")

    if not username or not password:
        return jsonify({'error': 'Username and password are required'}), 400

    try:
        # Query using SQLAlchemy ORM
        admin = db.session.query(Admin).filter_by(username=username).first()

        if admin:
            print(f"Admin found: {admin.username}")
            # Check password using bcrypt
            if bcrypt.checkpw(password.encode('utf-8'), admin.password_hash.encode('utf-8')):
                print("Password matches!")
                # Set session variables
                session['admin_id'] = admin.id
                session['admin_username'] = admin.username
                session['admin_name'] = admin.full_name
                session['admin_role'] = admin.role

                return jsonify({
                    'message': 'Login successful',
                    'admin': {
                        'id': admin.id,
                        'username': admin.username,
                        'name': admin.full_name,
                        'role': admin.role
                    }
                }), 200
            else:
                print("Password does not match!")
        else:
            print("Admin not found!")

        return jsonify({'error': 'Invalid username or password'}), 401
    except Exception as e:
        print(f"Error during login: {e}")
        return jsonify({'error': 'An internal error occurred during login'}), 500

@bp.route('/logout', methods=['POST'])
def logout():
    # Clear session variables
    session.pop('admin_id', None)
    session.pop('admin_username', None)
    session.pop('admin_name', None)
    session.pop('admin_role', None)

    return jsonify({'message': 'Logout successful'}), 200
