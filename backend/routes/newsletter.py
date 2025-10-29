from flask import Blueprint, jsonify, request
import re
from models import NewsletterSubscriber
from database import db

bp = Blueprint('newsletter', __name__)

def is_valid_email(email):
    """Validate email format"""
    email_regex = r'^[^\s@]+@[^\s@]+\.[^\s@]+$'
    return re.match(email_regex, email) is not None

@bp.route('/', methods=['POST'])
def subscribe():
    data = request.json
    email = data.get('email', '').strip()
    name = data.get('name', '').strip()

    if not email:
        return jsonify({'error': 'Email is required'}), 400

    if not is_valid_email(email):
        return jsonify({'error': 'Invalid email format'}), 400

    try:
        # Check if email already exists using ORM
        subscriber = db.session.query(NewsletterSubscriber).filter_by(email=email).first()

        if subscriber:
            if subscriber.status == 'active':
                return jsonify({'message': 'Email is already subscribed'}), 200
            else:
                # Reactivate if previously unsubscribed
                subscriber.status = 'active'
                subscriber.subscribed_at = db.func.current_timestamp() # Use database function
        else:
            # Create new subscriber
            new_subscriber = NewsletterSubscriber(
                email=email,
                name=name if name else None, # Store None if name is empty
                status='active'
            )
            db.session.add(new_subscriber)

        db.session.commit()
        return jsonify({'message': 'Successfully subscribed to newsletter'}), 201

    except Exception as e:
        db.session.rollback()
        print(f"Error during newsletter subscription: {e}")
        return jsonify({'error': 'An internal error occurred during subscription'}), 500
