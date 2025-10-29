-- Eternal Fusion Pavilion - Enhanced Database Schema

-- Drop existing tables if they exist (for clean migration)
DROP TABLE IF EXISTS audit_log CASCADE;
DROP TABLE IF EXISTS reservation_blocks CASCADE;
DROP TABLE IF EXISTS reservations CASCADE;
DROP TABLE IF EXISTS rooms CASCADE;
DROP TABLE IF EXISTS locations CASCADE;
DROP TABLE IF EXISTS newsletter_subscribers CASCADE;
DROP TABLE IF EXISTS customers CASCADE;
DROP TABLE IF EXISTS admins CASCADE;

-- Create locations table
CREATE TABLE locations (
    id SERIAL PRIMARY KEY,
    code VARCHAR(3) UNIQUE NOT NULL, -- JPN, ITA, ESP
    name VARCHAR(100) NOT NULL,
    timezone VARCHAR(50) NOT NULL,
    max_guests_per_slot INTEGER NOT NULL DEFAULT 120,
    max_reservations_per_slot INTEGER NOT NULL DEFAULT 30,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create rooms table
CREATE TABLE rooms (
    id SERIAL PRIMARY KEY,
    location_id INTEGER REFERENCES locations(id) ON DELETE CASCADE,
    code VARCHAR(10) UNIQUE NOT NULL, -- JPN-SP, ITA-FS, etc.
    name VARCHAR(100) NOT NULL,
    max_capacity INTEGER NOT NULL DEFAULT 30,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create customers table
CREATE TABLE customers (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    phone VARCHAR(20),
    newsletter_signup BOOLEAN DEFAULT false,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create admins table
CREATE TABLE admins (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(100) NOT NULL,
    role VARCHAR(20) NOT NULL DEFAULT 'admin'
        CHECK (role IN ('admin', 'manager')),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);


-- Create reservations table
CREATE TABLE reservations (
    id SERIAL PRIMARY KEY,
    reservation_number VARCHAR(20) UNIQUE NOT NULL, -- JPN-A43C7
    customer_id INTEGER REFERENCES customers(id) ON DELETE CASCADE,
    location_id INTEGER REFERENCES locations(id) ON DELETE CASCADE,
    room_id INTEGER REFERENCES rooms(id) ON DELETE SET NULL,
    date DATE NOT NULL,
    time TIME NOT NULL,
    duration_minutes INTEGER NOT NULL DEFAULT 60,
    -- max party_size constraint to 30 ---
    party_size INTEGER NOT NULL CHECK (party_size > 0 AND party_size <= 30),

    status VARCHAR(20) NOT NULL DEFAULT 'confirmed'
        CHECK (status IN ('confirmed', 'cancelled', 'no-show', 'completed')),
    special_requests TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create reservation_blocks table (for admin-created unavailable time ranges)
CREATE TABLE reservation_blocks (
    id SERIAL PRIMARY KEY,
    location_id INTEGER REFERENCES locations(id) ON DELETE CASCADE,
    room_id INTEGER REFERENCES rooms(id) ON DELETE CASCADE, -- NULL means location-wide block
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    start_time TIME NOT NULL,
    end_time TIME NOT NULL,
    block_type VARCHAR(10) NOT NULL CHECK (block_type IN ('hard', 'soft')),
    reason TEXT,
    created_by INTEGER REFERENCES admins(id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create newsletter_subscribers table
CREATE TABLE newsletter_subscribers (
    id SERIAL PRIMARY KEY,
    email VARCHAR(100) UNIQUE NOT NULL,
    name VARCHAR(100),
    status VARCHAR(20) NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'unsubscribed')),
    subscribed_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create audit log table for tracking manual overrides
CREATE TABLE audit_log (
    id SERIAL PRIMARY KEY,
    admin_id INTEGER REFERENCES admins(id),
    action VARCHAR(50) NOT NULL,
    entity_type VARCHAR(50) NOT NULL,
    entity_id INTEGER,
    details JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for performance
CREATE INDEX idx_reservations_date ON reservations(date);
CREATE INDEX idx_reservations_time ON reservations(time);
CREATE INDEX idx_reservations_location ON reservations(location_id);
CREATE INDEX idx_reservations_room ON reservations(room_id);
CREATE INDEX idx_reservations_status ON reservations(status);
CREATE INDEX idx_reservations_date_time ON reservations(date, time);
CREATE INDEX idx_rooms_location ON rooms(location_id);
CREATE INDEX idx_blocks_location ON reservation_blocks(location_id);
CREATE INDEX idx_blocks_room ON reservation_blocks(room_id);
CREATE INDEX idx_blocks_dates ON reservation_blocks(start_date, end_date);

-- Grant permissions
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO efp_user;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO efp_user;

-- Seed data for Eternal Fusion Pavilion

-- Insert locations
INSERT INTO locations (code, name, timezone, max_guests_per_slot, max_reservations_per_slot) VALUES
('JPN', 'Japan', 'Asia/Tokyo', 120, 30),
('ITA', 'Italy', 'Europe/Rome', 120, 30),
('ESP', 'Spain', 'Europe/Madrid', 120, 30);

-- Insert rooms for Japan
INSERT INTO rooms (location_id, code, name, max_capacity, is_active) VALUES
((SELECT id FROM locations WHERE code = 'JPN'), 'JPN-SP', 'Sakura Pavilion', 30, true),
((SELECT id FROM locations WHERE code = 'JPN'), 'JPN-KS', 'Kintsugi Salon', 30, true),
((SELECT id FROM locations WHERE code = 'JPN'), 'JPN-NG', 'Nami Gallery', 30, true),
((SELECT id FROM locations WHERE code = 'JPN'), 'JPN-HA', 'Hikari Atrium', 30, true),
((SELECT id FROM locations WHERE code = 'JPN'), 'JPN-TS', 'Tsukimi Suite', 30, true),
((SELECT id FROM locations WHERE code = 'JPN'), 'JPN-ZH', 'Zen Garden Hall', 30, true);

-- Insert rooms for Italy
INSERT INTO rooms (location_id, code, name, max_capacity, is_active) VALUES
((SELECT id FROM locations WHERE code = 'ITA'), 'ITA-FS', 'Florentine Studiolo', 30, true),
((SELECT id FROM locations WHERE code = 'ITA'), 'ITA-VS', 'Venetian Sala', 30, true),
((SELECT id FROM locations WHERE code = 'ITA'), 'ITA-TL', 'Tuscan Loggia', 30, true),
((SELECT id FROM locations WHERE code = 'ITA'), 'ITA-AT', 'Amalfi Terrace', 30, true),
((SELECT id FROM locations WHERE code = 'ITA'), 'ITA-BG', 'Baroque Galleria', 30, true),
((SELECT id FROM locations WHERE code = 'ITA'), 'ITA-TR', 'Trastevere Salon', 30, true);

-- Insert rooms for Spain
INSERT INTO rooms (location_id, code, name, max_capacity, is_active) VALUES
((SELECT id FROM locations WHERE code = 'ESP'), 'ESP-AP', 'Alhambra Patio', 30, true),
((SELECT id FROM locations WHERE code = 'ESP'), 'ESP-GS', 'Gaudí Salon', 30, true),
((SELECT id FROM locations WHERE code = 'ESP'), 'ESP-RB', 'Rioja Bodega', 30, true),
((SELECT id FROM locations WHERE code = 'ESP'), 'ESP-SR', 'Sevilla Azahar Room', 30, true),
((SELECT id FROM locations WHERE code = 'ESP'), 'ESP-CM', 'Catalan Modernista Hall', 30, true),
((SELECT id FROM locations WHERE code = 'ESP'), 'ESP-IM', 'Ibiza Mar Salon', 30, true);

-- Insert default admin user (password is 'strongpassword')
INSERT INTO admins (username, password_hash, full_name, role) VALUES
('admin', '$2b$12$YLi3OI7ZXzl64QJOSSae7.t7AWtSInsWJVCPnndYKH0tiOTe.09lC', 'Eternal Fusion Pavilion Administrator', 'admin');

-- Insert sample customers
INSERT INTO customers (name, email, phone, newsletter_signup) VALUES
('Akira Tanaka', 'akira.tanaka@example.com', '+81-3-1234-5678', true),
('Sofia Rossi', 'sofia.rossi@example.com', '+39-06-1234-5678', true),
('Carlos Garcia', 'carlos.garcia@example.com', '+34-91-123-4567', false);

-- Insert sample reservations
INSERT INTO reservations (
    reservation_number,
    customer_id,
    location_id,
    room_id,
    date,
    time,
    duration_minutes,
    party_size,
    status
) VALUES
(
    'JPN-A1B2C',
    (SELECT id FROM customers WHERE email = 'akira.tanaka@example.com'),
    (SELECT id FROM locations WHERE code = 'JPN'),
    (SELECT id FROM rooms WHERE code = 'JPN-SP'),
    CURRENT_DATE + INTERVAL '1 day',
    '19:00',
    60,
    4, -- party_size within original constraint
    'confirmed'
),
(
    'ITA-D3E4F',
    (SELECT id FROM customers WHERE email = 'sofia.rossi@example.com'),
    (SELECT id FROM locations WHERE code = 'ITA'),
    (SELECT id FROM rooms WHERE code = 'ITA-VS'),
    CURRENT_DATE + INTERVAL '2 days',
    '20:00',
    60,
    2, -- party_size within original constraint
    'confirmed'
);
