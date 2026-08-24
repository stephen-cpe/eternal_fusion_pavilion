from flask import Blueprint, jsonify, request, session
from models import Customer, NewsletterSubscriber
from database import db 
from utils.audit import log_audit
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
    # Only treat newsletter_signup as provided when the key is actually present,
    # so unrelated profile edits don't silently reset the subscription preference.
    newsletter_signup = data.get('newsletter_signup') if 'newsletter_signup' in data else None

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
        # Only update newsletter_signup when the caller explicitly provided it;
        # otherwise preserve the existing value (fixes silent unsubscribe on
        # name/email/phone-only edits).
        if newsletter_signup is not None:
            customer.newsletter_signup = bool(newsletter_signup)
            # Sync to newsletter_subscribers so the Newsletter admin page
            # stays consistent with the Customers admin page.
            subscriber = db.session.query(NewsletterSubscriber).filter_by(
                email=customer.email
            ).first()
            if bool(newsletter_signup):
                # Subscribing: create or reactivate the subscriber row.
                if subscriber:
                    subscriber.status = 'active'
                else:
                    db.session.add(NewsletterSubscriber(
                        email=customer.email,
                        name=customer.name,
                        status='active',
                    ))
            else:
                # Unsubscribing: mark the subscriber row inactive.
                if subscriber:
                    subscriber.status = 'inactive'

        # Log the audit
        log_audit(
            admin_id=session['admin_id'],
            action='update_customer',
            entity_type='customer',
            entity_id=customer_id,
            details={"old": old_details, "new": data},
        )
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
