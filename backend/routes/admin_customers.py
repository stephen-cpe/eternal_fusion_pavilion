from flask import Blueprint, jsonify, request, session
from models import Customer, NewsletterSubscriber, AuditLog 
from database import db 
from sqlalchemy import or_ # For searching multiple fields

bp = Blueprint('admin_customers', __name__)

@bp.route('/customers', methods=['GET'])
def get_customers():
    """Get customers using ORM."""
    if 'admin_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    try:
        # Simple query for all customers, ordered by ID
        customers = db.session.query(Customer).order_by(Customer.id).all()
        result = [customer.to_dict() for customer in customers]
        return jsonify(result)
    except Exception as e:
        print(f"Error fetching customers: {e}")
        return jsonify({'error': 'An internal error occurred'}), 500
    
@bp.route('/customers/<int:customer_id>', methods=['PUT'])
def update_customer(customer_id):
    """Update a customer's details."""
    if 'admin_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    data = request.json
    name = data.get('name', '').strip()
    email = data.get('email', '').strip()
    phone = data.get('phone', '').strip()
    newsletter_signup = data.get('newsletter_signup', False)

    if not name or not email:
        return jsonify({'error': 'Name and email are required'}), 400

    try:
        customer = db.session.get(Customer, customer_id)
        if not customer:
            return jsonify({'error': 'Customer not found'}), 404

        # Check for email conflict
        if email != customer.email:
            existing = db.session.query(Customer).filter(
                Customer.email == email,
                Customer.id != customer_id
            ).first()
            if existing:
                return jsonify({'error': 'This email address is already in use by another customer'}), 409

        # Log details before change
        old_details = {
            "name": customer.name,
            "email": customer.email,
            "phone": customer.phone,
            "newsletter_signup": customer.newsletter_signup
        }
        
        # Apply updates
        customer.name = name
        customer.email = email
        customer.phone = phone
        customer.newsletter_signup = newsletter_signup

        # Log the audit
        log_entry = AuditLog(
            admin_id=session['admin_id'],
            action='update_customer',
            entity_type='customer',
            entity_id=customer_id,
            details={
                "old": old_details,
                "new": data
            }
        )
        db.session.add(log_entry)
        db.session.commit()

        return jsonify({'message': 'Customer updated successfully'})

    except Exception as e:
        db.session.rollback()
        print(f"Error updating customer: {e}")
        return jsonify({'error': 'An internal error occurred'}), 500

@bp.route('/subscribers', methods=['GET'])
def get_subscribers():
    """Get newsletter subscribers using ORM."""
    if 'admin_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    try:
        subscribers = db.session.query(NewsletterSubscriber).order_by(NewsletterSubscriber.id).all()
        result = [sub.to_dict() for sub in subscribers]
        return jsonify(result)
    except Exception as e:
        print(f"Error fetching subscribers: {e}")
        return jsonify({'error': 'An internal error occurred'}), 500

# Potential future routes:
# - Update subscriber status
