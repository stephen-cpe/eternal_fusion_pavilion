from database import db
from datetime import datetime
import json

# Helper function for serialization
def _datetime_handler(x):
    if isinstance(x, datetime):
        return x.isoformat()
    raise TypeError("Unknown type")

class Location(db.Model):
    __tablename__ = 'locations'
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(3), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    timezone = db.Column(db.String(50), nullable=False)
    max_guests_per_slot = db.Column(db.Integer, nullable=False, default=120)
    max_reservations_per_slot = db.Column(db.Integer, nullable=False, default=30)
    created_at = db.Column(db.DateTime(timezone=True), server_default=db.func.current_timestamp())

    rooms = db.relationship('Room', back_populates='location', cascade='all, delete-orphan')
    reservations = db.relationship('Reservation', back_populates='location', cascade='all, delete-orphan')
    reservation_blocks = db.relationship('ReservationBlock', back_populates='location', cascade='all, delete-orphan')

    def to_dict(self):
        return {
            'id': self.id,
            'code': self.code,
            'name': self.name,
            'timezone': self.timezone,
            'max_guests_per_slot': self.max_guests_per_slot,
            'max_reservations_per_slot': self.max_reservations_per_slot,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

class Room(db.Model):
    __tablename__ = 'rooms'
    id = db.Column(db.Integer, primary_key=True)
    location_id = db.Column(db.Integer, db.ForeignKey('locations.id', ondelete='CASCADE'), nullable=False)
    code = db.Column(db.String(10), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    max_capacity = db.Column(db.Integer, nullable=False, default=30)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime(timezone=True), server_default=db.func.current_timestamp())

    location = db.relationship('Location', back_populates='rooms')
    reservations = db.relationship('Reservation', back_populates='room') # backref might conflict if reservation also has 'room'
    reservation_blocks = db.relationship('ReservationBlock', back_populates='room', cascade='all, delete-orphan')

    def to_dict(self):
        return {
            'id': self.id,
            'location_id': self.location_id,
            'code': self.code,
            'name': self.name,
            'max_capacity': self.max_capacity,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

class Customer(db.Model):
    __tablename__ = 'customers'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    phone = db.Column(db.String(20))
    newsletter_signup = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime(timezone=True), server_default=db.func.current_timestamp())
    updated_at = db.Column(db.DateTime(timezone=True), server_default=db.func.current_timestamp(), onupdate=db.func.current_timestamp())

    reservations = db.relationship('Reservation', back_populates='customer', cascade='all, delete-orphan')

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'email': self.email,
            'phone': self.phone,
            'newsletter_signup': self.newsletter_signup,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

class Admin(db.Model):
    __tablename__ = 'admins'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    full_name = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='admin')
    created_at = db.Column(db.DateTime(timezone=True), server_default=db.func.current_timestamp())

    reservation_blocks_created = db.relationship('ReservationBlock', back_populates='creator')
    audit_logs = db.relationship('AuditLog', back_populates='admin')

    def to_dict(self, include_hash=False):
        data = {
            'id': self.id,
            'username': self.username,
            'full_name': self.full_name,
            'role': self.role,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
        if include_hash:
             data['password_hash'] = self.password_hash
        return data

class Reservation(db.Model):
    __tablename__ = 'reservations'
    id = db.Column(db.Integer, primary_key=True)
    reservation_number = db.Column(db.String(20), unique=True, nullable=False)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id', ondelete='CASCADE'), nullable=False)
    location_id = db.Column(db.Integer, db.ForeignKey('locations.id', ondelete='CASCADE'), nullable=False)
    room_id = db.Column(db.Integer, db.ForeignKey('rooms.id', ondelete='SET NULL'))
    date = db.Column(db.Date, nullable=False)
    time = db.Column(db.Time, nullable=False)
    duration_minutes = db.Column(db.Integer, nullable=False, default=60)
    party_size = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(20), nullable=False, default='confirmed')
    special_requests = db.Column(db.Text)
    created_at = db.Column(db.DateTime(timezone=True), server_default=db.func.current_timestamp())
    updated_at = db.Column(db.DateTime(timezone=True), server_default=db.func.current_timestamp(), onupdate=db.func.current_timestamp())

    customer = db.relationship('Customer', back_populates='reservations')
    location = db.relationship('Location', back_populates='reservations')
    room = db.relationship('Room', back_populates='reservations')

    def to_dict(self):
        return {
            'id': self.id,
            'reservation_number': self.reservation_number,
            'customer_id': self.customer_id,
            'location_id': self.location_id,
            'room_id': self.room_id,
            'date': self.date.isoformat() if self.date else None,
            'time': self.time.strftime('%H:%M') if self.time else None,
            'duration_minutes': self.duration_minutes,
            'party_size': self.party_size,
            'status': self.status,
            'special_requests': self.special_requests,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            # Include related objects if needed, handle potential None values
            'customer': self.customer.to_dict() if self.customer else None,
            'location': {'code': self.location.code, 'name': self.location.name} if self.location else None,
            'room': {'code': self.room.code, 'name': self.room.name} if self.room else None,
        }

class ReservationBlock(db.Model):
    __tablename__ = 'reservation_blocks'
    id = db.Column(db.Integer, primary_key=True)
    location_id = db.Column(db.Integer, db.ForeignKey('locations.id', ondelete='CASCADE'), nullable=False)
    room_id = db.Column(db.Integer, db.ForeignKey('rooms.id', ondelete='CASCADE')) # Can be NULL
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)
    block_type = db.Column(db.String(10), nullable=False)
    reason = db.Column(db.Text)
    created_by = db.Column(db.Integer, db.ForeignKey('admins.id'))
    created_at = db.Column(db.DateTime(timezone=True), server_default=db.func.current_timestamp())

    location = db.relationship('Location', back_populates='reservation_blocks')
    room = db.relationship('Room', back_populates='reservation_blocks')
    creator = db.relationship('Admin', back_populates='reservation_blocks_created')

    def to_dict(self):
        return {
            'id': self.id,
            'location_id': self.location_id,
            'room_id': self.room_id,
            'start_date': self.start_date.isoformat() if self.start_date else None,
            'end_date': self.end_date.isoformat() if self.end_date else None,
            'start_time': self.start_time.strftime('%H:%M') if self.start_time else None,
            'end_time': self.end_time.strftime('%H:%M') if self.end_time else None,
            'block_type': self.block_type,
            'reason': self.reason,
            'created_by': self.created_by,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            # Include related objects if needed
            'location_name': self.location.name if self.location else None,
            'room_name': self.room.name if self.room else None,
            'created_by_name': self.creator.full_name if self.creator else None,
        }


class NewsletterSubscriber(db.Model):
    __tablename__ = 'newsletter_subscribers'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100), unique=True, nullable=False)
    name = db.Column(db.String(100))
    status = db.Column(db.String(20), nullable=False, default='active')
    subscribed_at = db.Column(db.DateTime(timezone=True), server_default=db.func.current_timestamp())

    def to_dict(self):
        return {
            'id': self.id,
            'email': self.email,
            'name': self.name,
            'status': self.status,
            'subscribed_at': self.subscribed_at.isoformat() if self.subscribed_at else None
        }

class AuditLog(db.Model):
    __tablename__ = 'audit_log'
    id = db.Column(db.Integer, primary_key=True)
    admin_id = db.Column(db.Integer, db.ForeignKey('admins.id'))
    action = db.Column(db.String(50), nullable=False)
    entity_type = db.Column(db.String(50), nullable=False)
    entity_id = db.Column(db.Integer)
    details = db.Column(db.JSON) # Use JSON type if your DB supports it
    created_at = db.Column(db.DateTime(timezone=True), server_default=db.func.current_timestamp())

    admin = db.relationship('Admin', back_populates='audit_logs')

    def to_dict(self):
        # Handle JSON serialization carefully
        details_json = self.details
        if isinstance(self.details, str): # Handle if details were stored as string
             try:
                 details_json = json.loads(self.details)
             except json.JSONDecodeError:
                 details_json = {"raw": self.details} # Fallback
        elif not isinstance(self.details, (dict, list, type(None))):
             details_json = str(self.details) # Fallback for other types

        return {
            'id': self.id,
            'admin_id': self.admin_id,
            'action': self.action,
            'entity_type': self.entity_type,
            'entity_id': self.entity_id,
            'details': details_json,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'admin_name': self.admin.full_name if self.admin else None,
        }
