# Software Requirement Specification
# Eternal Fusion Pavilion - Reservation Management System

---

## 1. Introduction

### 1.1 Purpose

This document specifies the software requirements for the Eternal Fusion Pavilion (EFP) Reservation Management System. It describes the system's functional and non-functional requirements, its interfaces, and its high-level architecture. This system is a full-stack web application designed to manage restaurant reservations across multiple international locations.

### 1.2 Scope

The system provides two primary interfaces:

1.  **Public-Facing Frontend:** A React Single Page Application (SPA) that allows potential customers to view restaurant locations, check reservation availability, and book a table. It also includes a newsletter subscription form.
2.  **Admin Backend:** A secure Flask REST API and corresponding React-based admin dashboard. This interface is for restaurant staff and managers to perform secure login, manage all reservations, manually create bookings, manage customer data, define unavailable time blocks, and audit administrative actions.

### 1.3 Definitions and Acronyms

| Term | Definition |
| :--- | :--- |
| **EFP** | Eternal Fusion Pavilion. The name of the restaurant and this software system. |
| **System** | The EFP Reservation Management System as a whole. |
| **SPA** | Single Page Application. The React frontend. |
| **API** | Application Programming Interface. The Flask backend. |
| **Public User** | A non-authenticated user (customer) accessing the public website. |
| **Admin User** | An authenticated staff member with privileged access. |
| **Admin** | A standard Admin User role. |
| **Manager** | An Admin User role with elevated privileges (e.g., overriding soft blocks). |
| **Block** | A period of time, defined by an Admin, when reservations are not available. |
| **Hard Block** | A reservation block that cannot be overridden by any user. |
| **Soft Block** | A reservation block that can only be overridden by a user with the 'Manager' role. |
| **Dining Hours** | Service hours defined in `utils/time_utils.py`. Tuesday–Saturday 17:00–23:00; Sunday & Monday 17:00–21:00. |
| **Slot** | A 30-minute dining interval generated from the dining hours for a given date. |

---

## 2. Overall Description

### 2.1 Product Perspective

The EFP is a self-contained, client-server system. It is composed of three main components:

1.  **Frontend:** A React SPA (built with Vite) that runs in the user's web browser. It communicates with the backend via HTTP requests. The dev server runs on port 3000 and proxies `/api` requests to the Flask backend on port 5000 (`vite.config.mjs`). The production build outputs static files to `frontend/dist`, which are served by Nginx (or Flask's catch-all route in development).
2.  **Backend:** A Python Flask server that exposes a JSON-based REST API. It handles all business logic, data validation, and authentication. Routes are organized as Flask Blueprints registered under the configurable `API_PREFIX` (default `/api`). Shared helpers live in `utils/` (`time_utils.py`, `room_assignment.py`, `audit.py`, `dashboard.py`).
3.  **Database:** A PostgreSQL database, interacted with via the Flask backend using SQLAlchemy (ORM, primary data access layer in `models.py` and route handlers) and `psycopg2` (direct connection pool in `database.py`, used by the utility functions in `utils/room_assignment.py` for constraint queries).

### 2.2 Product Functions

The system shall provide the following high-level functions:

* **Public Users:**
    * View restaurant locations and information.
    * Check real-time reservation availability for a specific location and date.
    * Submit a new reservation request.
    * Subscribe to a marketing newsletter.

* **Admin Users:**
    * Securely log in and out of the admin dashboard.
    * View a "dashboard" with at-a-glance statistics and a room occupancy "heatmap" for a given day.
    * Perform full CRUD (Create, Read, Update, Delete) operations on all reservations.
    * Manually override the room assignment of an existing reservation.
    * Perform CRUD operations on customer records (read + update are implemented; create/delete are indirect via reservation creation).
    * Perform CRUD operations on reservation blocks (availability management).
    * View the list of rooms for a location (used by block/reservation editors).
    * View a list of all newsletter subscribers.
    * View an audit log of all significant admin actions.
    * Manage their own admin profile (name, password).

### 2.2.1 Frontend Application Inventory

The public SPA (`src/App.jsx`) exposes the following routes: `/` (Home), `/menu`, `/about`, `/reservations`, `/gallery`, and `/admin` (login). Protected admin routes (under `/admin/*`, guarded by `ProtectedRoute`) render within `AdminLayout` and include: Dashboard, Reservations, Blocks, Customers, Newsletter, and Audit Log. The admin UI components include `AdminNavigation`, `AddReservationModal`, `EditReservationModal`, `EditCustomerModal`, `ChangeNameModal`, and `ChangePasswordModal`.

### 2.3 User Characteristics

| User Role | Description | Permissions |
| :--- | :--- | :--- |
| **Public User** | Any individual accessing the public website. | Read-only access to locations and availability. Can create new reservations and newsletter subscriptions. |
| **Admin** | A staff member with a registered account. | Full CRUD on reservations, customers, and blocks. Cannot override 'soft' blocks. |
| **Manager** | A staff member with the `manager` role. | All 'Admin' permissions, plus the ability to override 'soft' reservation blocks. |

### 2.4 Operating Environment

* **Frontend:** The system shall be operable in all modern, JavaScript-enabled web browsers (e.g., Chrome, Firefox, Safari, Edge). Built with React 19 and Vite 8, styled with Tailwind CSS 4, with `@tanstack/react-query` for server state, `axios` for HTTP, `react-toastify` for notifications, and `framer-motion` for animations. Vite proxies `/api/*` to the backend during development. Testing is via Vitest + `@testing-library/react`.
* **Backend:** The system shall run in a Python 3 environment (Flask 3.1 with Flask-Session 0.8, Flask-SQLAlchemy 3.1, Flask-Cors 6.0, bcrypt, and psycopg2-binary). Gunicorn is used as the WSGI server in production. Testing is via pytest + pytest-flask.
* **Database:** The system requires a running PostgreSQL database instance.

### 2.5 Design and Implementation Constraints

* The frontend and backend must be decoupled.
* All communication between frontend and backend must be via the JSON-based REST API.
* The backend must be stateless (from an application perspective), relying on server-side filesystem sessions (`Flask-Session`, `SESSION_TYPE='filesystem'`, stored under `backend/.flask_session/`) for managing authentication state.
* CORS is enabled for the `/api/*` path with `supports_credentials=True`, allowing the configured development origins (`localhost:3000`, `127.0.0.1:3000`, and the host machine's LAN IP on port 3000).
* All admin-level API endpoints (excluding `/login`) must be protected and require an active, authenticated session.
* Admin passwords must be securely hashed in the database using `bcrypt`.
* The system shall use a weighted-random algorithm for automatic room assignment.
* The database structure is fixed as defined in the `init_db.sql` schema.
* Configuration is loaded from environment variables via `python-dotenv` (`backend/config.py`); a standalone `backend/create_admin.py` script is provided to (re)seed the default admin account.
* The system includes an automated test suite: backend tests run via `pytest` (unit tests for `utils/` + integration tests for all route blueprints, using SQLite in-memory); frontend tests run via `Vitest` + `@testing-library/react` (service-layer and component tests). Tests are executed with `cd backend && pytest tests/` and `cd frontend && npm test` respectively.

---

## 3. Specific Requirements

### 3.1 Database Schema Requirements

The system must persist data according to the following schema.

| Table | Purpose | Key Fields |
| :--- | :--- | :--- |
| `locations` | Stores the restaurant branches. | `id`, `code` (3-char unique), `name`, `timezone`, `max_guests_per_slot`, `max_reservations_per_slot` |
| `rooms` | Stores bookable rooms within a location. | `id`, `location_id` (FK), `code` (unique), `name`, `max_capacity`, `is_active` |
| `customers` | Stores guest information. | `id`, `name`, `email` (unique), `phone`, `newsletter_signup` |
| `admins` | Stores admin user accounts. | `id`, `username` (unique), `password_hash`, `full_name`, `role` ('admin' or 'manager') |
| `reservations` | Core table for all bookings. | `id`, `reservation_number` (unique), `customer_id` (FK ON DELETE CASCADE), `location_id` (FK ON DELETE CASCADE), `room_id` (FK ON DELETE SET NULL), `date`, `time`, `duration_minutes` (default 60), `party_size` (CHECK `> 0 AND <= 30`), `status` (CHECK in 'confirmed','cancelled','no-show','completed'), `special_requests` |
| `reservation_blocks` | Admin-defined unavailable times. | `id`, `location_id` (FK ON DELETE CASCADE), `room_id` (FK ON DELETE CASCADE, nullable), `start_date`, `end_date`, `start_time`, `end_time`, `block_type` (CHECK 'hard'/'soft'), `reason`, `created_by` (FK to admins) |
| `newsletter_subscribers` | List of newsletter signups. | `id`, `email` (unique), `name`, `status` ('active' or 'unsubscribed') |
| `audit_log` | Tracks admin actions. | `id`, `admin_id` (FK), `action`, `entity_type`, `entity_id`, `details` (JSONB) |

**Seed Data (`init_db.sql`):** Three locations (JPN, ITA, ESP) each with 6 rooms (`max_capacity=30`); one default admin (`admin` / `strongpassword`, role `admin`); three sample customers; two sample reservations. Indexes are created on `reservations(date)`, `reservations(time)`, `reservations(location_id)`, `reservations(room_id)`, `reservations(status)`, `reservations(date, time)`, `rooms(location_id)`, and `reservation_blocks(location_id)`, `reservation_blocks(room_id)`, `reservation_blocks(start_date, end_date)`.

### 3.2 Functional Requirements

#### FR1: Public User Module

* **FR1.1: View Locations**
    * The system shall provide a public API endpoint (`GET /api/reservations/locations`) to list all `locations` ordered by name. The response returns `{ "locations": [ ... ] }`.

* **FR1.2: Check Availability**
    * The system shall provide a public API endpoint (`GET /api/reservations/availability`) that accepts a `location_id` and `date` (YYYY-MM-DD).
    * It shall reject requests for past dates (HTTP 400).
    * It shall return a list of all 30-minute time slots for that day's dining hours (per `utils/time_utils.py`), along with a boolean `available` status, `slotsLeft`, and `guestsAvailable` for each.
    * The `available` status must be `false` if `validate_reservation_constraints` (FR4) fails for a 1-guest party.

* **FR1.3: Create Reservation**
    * The system shall provide a public API endpoint (`POST /api/reservations/`) to create a new reservation.
    * **FR1.3.1 (Input):** The endpoint shall require `location_id`, `date`, `time`, `party_size`, `name`, and `email`. The `phone` and `special_requests` fields are optional.
    * **FR1.3.2 (Customer):** The system shall find a `customer` by `email`. If found, it shall update the customer's `name` and `phone` from the request and refresh `updated_at`. If not found, it shall create a new customer (with `newsletter_signup=false`).
    * **FR1.3.3 (Validation - Party):** The system must reject the request if `party_size` is not between 1 and 12 (inclusive). The error response includes a `requiresCall: true` flag when `party_size > 12`.
    * **FR1.3.4 (Validation - Date/Time):** The system must reject past dates and times outside the dining hours for the given `date` (as defined in `utils/time_utils.py`).
    * **FR1.3.5 (Validation - Constraints):** The system must validate the request against all reservation constraints (see FR4). The default `duration_minutes` is 60.
    * **FR1.3.6 (Room Assignment):** On successful validation, the system must automatically assign a `room_id` using the logic in FR5.
    * **FR1.3.7 (Output):** The system shall generate a unique `reservation_number` (format `LOC-XXXXX`, e.g., "JPN-A1B2C", generated by `utils/room_assignment.generate_reservation_number`), save the reservation with `status='confirmed'`, and return HTTP 201 with `{ id, reservationNumber, message, room: { code, name } }`.

* **FR1.4: Newsletter Subscription**
    * The system shall provide a public API endpoint (`POST /api/newsletter/`) to subscribe a user.
    * The endpoint shall validate the email format and return HTTP 400 on invalid/missing email.
    * If the email does not exist, it shall be created with 'active' status (HTTP 201).
    * If the email exists and is 'active', it shall return a "already subscribed" message (HTTP 200).
    * If the email exists and is 'unsubscribed', its status shall be updated to 'active' and `subscribed_at` refreshed.

#### FR2: Admin Authentication Module

* **FR2.1: Login**
    * The system shall provide an endpoint (`POST /api/admin/login`) for an Admin User to authenticate.
    * The system must validate the `username` and `password` (using `bcrypt.checkpw`).
    * On success, the system must create a server-side session storing `admin_id`, `admin_username`, `admin_name`, and `admin_role`, and return the admin's `id`, `username`, `name`, and `role`.

* **FR2.2: Logout**
    * The system shall provide an endpoint (`POST /api/admin/logout`) that clears all admin-related session data.

* **FR2.3: Access Control**
    * All API endpoints under the `/api/admin/` path (except `/login`) must be protected.
    * Each protected handler checks for `admin_id` in the session and returns an HTTP 401 Unauthorized error if absent. (Role checks for 'manager' are enforced at specific soft-block override points rather than at the blueprint level.)

#### FR3: Admin Reservation Management (CRUD)

* **FR3.1: Create Reservation (Admin)**
    * The system shall provide a protected endpoint (`POST /api/admin/reservations/create`) for admins.
    * **FR3.1.1 (Party Size):** This endpoint shall allow a `party_size` between 1 and 30.
    * **FR3.1.2 (Manual Room):** The endpoint shall optionally accept a `room_id`.
    * **FR3.1.3 (Room Validation):** If a `room_id` is provided, the system must validate it against `reservation_blocks` (FR4.4) and `rooms.max_capacity` (FR4.5).
    * **FR3.1.4 (Role Validation):** If the manually selected room is 'soft' blocked, the system must reject the request (HTTP 403) unless the authenticated user's role is 'manager'.
    * **FR3.1.5 (Auto-Assignment):** If no `room_id` is provided, the system shall use the logic in FR5 to assign one. If the only available auto-assigned room is soft-blocked and the user is not a 'manager', the request is rejected (HTTP 403).
    * **FR3.1.6 (Customer):** The system shall find or create the customer by `customer_email`, updating `name`/`phone` on an existing record.
    * **FR3.1.7 (Default Status):** Admin-created reservations are saved with `status='confirmed'`.
    * **FR3.1.8 (Auditing):** This action must be logged (see FR9.1).

* **FR3.2: Read Reservations**
    * The system shall provide a protected endpoint (`GET /api/admin/reservations`) to list reservations.
    * It must be filterable by `location_id`, `date` (YYYY-MM-DD), and a string `search` (querying `reservation_number`, `customer.name`, and `customer.email` via case-insensitive `ILIKE`).
    * Results are ordered by `date` descending, then `time` descending, and include eagerly loaded `customer`, `location` (`code`/`name`), and `room` (`code`/`name`) nested objects.

* **FR3.3: Update Reservation Status**
    * The system shall provide a protected endpoint (`PUT /api/admin/reservations/<id>/status`) to update only the `status` field.
    * Valid statuses are: 'confirmed', 'cancelled', 'no-show', 'completed'.
    * **FR3.3.1 (Auditing):** This action must be logged (see FR9.1).

* **FR3.4: Update Reservation Details**
    * The system shall provide a protected endpoint (`PUT /api/admin/reservations/<id>/details`) to update all reservation data.
    * Required input fields: `location_id`, `date`, `time`, `party_size`, `customer_name`, `customer_email`, `status` (plus optional `duration_minutes`, `room_id`, `customer_phone`, `special_requests`).
    * The system must re-validate all constraints (FR4) and room assignments (FR5) as if it were a new booking, but excluding its own ID from capacity calculations.
    * **FR3.4.1 (Auditing):** This action must be logged (see FR9.1).

* **FR3.5: Update Reservation Room (Manual Override)**
    * The system shall provide a protected endpoint (`PUT /api/admin/reservations/<id>/room`) to manually change the `room_id` of an existing reservation.
    * This endpoint must validate that the new room belongs to the same `location_id` as the reservation, that it is not 'hard' blocked (FR4.4), and that it has sufficient capacity (FR4.5).
    * **FR3.5.1 (Role Validation):** This action must reject (HTTP 403) if the new room is 'soft' blocked and the user is not a 'manager'.
    * **FR3.5.2 (Auditing):** This action must be logged (see FR9.1), including the `soft_block_override` flag, the old and new `room_id`.

* **FR3.6: Delete Reservation**
    * The system shall provide a protected endpoint (`DELETE /api/admin/reservations/<id>`) to delete a reservation.
    * **FR3.6.1 (Auditing):** This action must be logged (see FR9.1).

#### FR4: Reservation Constraint Logic (Backend)

The system must enforce the following rules, primarily via `utils/room_assignment.py` (`validate_reservation_constraints` and its helpers `check_location_blocks`, `calculate_location_occupancy`, `check_room_blocks`, `calculate_room_occupancy`).

* **FR4.1: Party Size Bounds**
    * Public bookings must have `1 <= party_size <= 12`. Admin bookings must have `1 <= party_size <= 30`. The DB-level `CHECK` constraint on `reservations.party_size` enforces `> 0 AND <= 30` regardless of caller.

* **FR4.2: Location Guest Limit**
    * The system must reject any new reservation if `(current_guests_in_slot + new_party_size) > locations.max_guests_per_slot`.
    * `current_guests_in_slot` is the sum of `party_size` from all confirmed `reservations` that overlap with the new reservation's time window (`time < end_time` and `time + duration < start_time` is the non-overlap condition; status must be 'confirmed').

* **FR4.3: Location Reservation Limit**
    * The system must reject any new reservation if `(current_reservations_in_slot + 1) > locations.max_reservations_per_slot`.
    * `current_reservations_in_slot` is the count of all confirmed `reservations` that overlap with the new reservation's time window.

* **FR4.4: Location 'Hard' Block**
    * The system must reject any new reservation if its time window overlaps with a `reservation_blocks` entry where `location_id` matches, `room_id` IS NULL, and `block_type` is 'hard'. Overlap is checked by: the reservation `date` is between `start_date` and `end_date`, and either (a) `start_time = end_time` (an all-day block that blocks any time on that date), or (b) `start_time < block.end_time` and `end_time > block.start_time`.

* **FR4.5: Room 'Hard' Block**
    * The system must reject any new reservation if its assigned room's time window overlaps with a `reservation_blocks` entry where `room_id` matches and `block_type` is 'hard' (same overlap rule as FR4.4, including the all-day `start_time = end_time` case).

* **FR4.6: Room Capacity**
    * The system must reject any new reservation if `(current_room_occupancy + new_party_size) > rooms.max_capacity` for the assigned room.
    * `current_room_occupancy` is the sum of `party_size` from all confirmed `reservations` in that specific room that overlap with the new reservation's time window.

#### FR5: Automatic Room Assignment Logic (Backend)

Implemented in `utils/room_assignment.py` (`get_candidate_rooms` and `weighted_random_room_selection`), using the psycopg2 connection pool.

* **FR5.1: Candidate Retrieval**
    * When auto-assigning a room, the system must first query all `rooms` for the `location_id` that are `is_active = true`.

* **FR5.2: Candidate Filtering**
    * The system must filter the candidate list, removing any room that:
        1.  Is 'hard' blocked (per FR4.4).
        2.  Has insufficient remaining capacity for the party, i.e., `(max_capacity - current_room_occupancy) < party_size` (per FR4.5).

* **FR5.3: Weighted-Random Selection**
    * From the final list of candidates, the system must perform a weighted-random selection (Python `random.choices`).
    * The `weight` for each room must be calculated as: `(available_capacity * 1000) + (100 - reservation_count)`, where `available_capacity = max_capacity - current_room_occupancy` and `reservation_count` is the number of confirmed reservations overlapping the slot in that room.
    * This algorithm prioritizes rooms with more available capacity, using the reservation count as a tie-breaker.
    * If no candidates remain, the assignment returns `None` and the calling handler rejects the booking.

#### FR6: Admin Dashboard & Lookup Module

* **FR6.1: Dashboard Statistics**
    * The system shall provide a protected endpoint (`GET /api/admin/dashboard/stats`) that accepts a `location_id` and `date` (both required).
    * It must return a comprehensive JSON object containing:
        1.  `location` details (via `Location.to_dict`).
        2.  `date` (the requested date string).
        3.  `time_slots`: the 30-minute slots for that date.
        4.  `room_heatmap`: a list of per-room objects (each with `id`, `code`, `name`, `max_capacity`, `is_active`, and a `slots` map). Each slot entry contains `occupancy`, `reservation_count`, and `percentage` (occupancy vs. `max_capacity`).
        5.  `location_stats`: a per-slot object detailing `total_guests`, `total_reservations`, `guests_percentage`, and `reservations_percentage` (vs. `max_guests_per_slot` / `max_reservations_per_slot`).
        6.  `reservations`: the full list of confirmed-and-other reservations for the day (serialized via `Reservation.to_dict`).
    * Only reservations with `status='confirmed'` contribute to heatmap occupancy and location stats.

* **FR6.2: Rooms Lookup**
    * The system shall provide a protected endpoint (`GET /api/admin/rooms`) that requires a `location_id` query parameter and returns the list of rooms for that location ordered by `code`. Used by the admin block and reservation editors.

#### FR7: Admin Block Management

* **FR7.1: Create Block**
    * The system shall provide a protected endpoint (`POST /api/admin/blocks`) to create a `reservation_blocks` entry.
    * Required fields: `location_id`, `start_date`, `end_date`, `start_time`, `end_time`, `block_type` (must be 'hard' or 'soft'). Optional: `room_id` (empty string is normalized to NULL for a location-wide block), `reason`. `created_by` is set to the session admin.
    * **FR7.1.1 (Auditing):** This action must be logged (see FR9.1).

* **FR7.2: Read Blocks**
    * The system shall provide a protected endpoint (`GET /api/admin/blocks`) to list all blocks, filterable by `location_id`. Results are ordered by `start_date` then `start_time` descending, and include eager-loaded `location`, `room`, and `creator` for `location_name`, `room_name`, and `created_by_name`.

* **FR7.3: Delete Block**
    * The system shall provide a protected endpoint (`DELETE /api/admin/blocks/<id>`) to delete a block.
    * **FR7.3.1 (Auditing):** This action must be logged (see FR9.1).

#### FR8: Admin Customer & Subscriber Management

* **FR8.1: Read Customers**
    * The system shall provide a protected endpoint (`GET /api/admin/customers`) to list all `customers` ordered by `id`.

* **FR8.2: Update Customer**
    * The system shall provide a protected endpoint (`PUT /api/admin/customers/<id>`) to update a customer's `name`, `email`, `phone`, and `newsletter_signup` status (`name` and `email` required).
    * The system must enforce that the new `email` is not already in use by another customer (HTTP 409).
    * **FR8.2.1 (Auditing):** This action must be logged (see FR9.1), capturing old and new values.

* **FR8.3: Read Subscribers**
    * The system shall provide a protected endpoint (`GET /api/admin/subscribers`) to list all `newsletter_subscribers` ordered by `id`.

#### FR9: Auditing & Profile Management

* **FR9.1: Audit Log Creation**
    * The system must automatically create an `audit_log` entry when any of the following admin actions are successfully committed:
        * `create_block`
        * `delete_block`
        * `update_customer`
        * `update_status` (reservation)
        * `update_details` (reservation)
        * `delete_reservation`
        * `manual_room_override`
        * `create_reservation`
    * Each entry records `admin_id`, `action`, `entity_type`, `entity_id`, and a JSON `details` payload whose shape is specific to the action.

* **FR9.2: Read Audit Log**
    * The system shall provide a protected endpoint (`GET /api/admin/audit-log`) to retrieve log entries, ordered by `created_at` descending.
    * It accepts an optional `limit` query parameter (integer, default 50) to cap the number of returned entries. The admin's `full_name` is included as `admin_name` via eager loading.

* **FR9.3: Admin Profile**
    * The system shall provide a protected endpoint (`GET /api/admin/profile`) returning the current admin's `username`, `fullName`, and `role` (used by the frontend to verify the session is still valid).
    * The system shall provide protected endpoints for an admin to update their own `full_name` (`PUT /api/admin/profile/name`, body `{ fullName }`; also updates the session's `admin_name`) and `password` (`PUT /api/admin/profile/password`, body `{ currentPassword, newPassword, confirmPassword }`; verifies the current password with bcrypt before updating).

#### FR10: Operational Endpoints

* **FR10.1: Health Check**
    * The system shall provide a public endpoint (`GET /api/health`) that executes `SELECT 1` via SQLAlchemy and returns `{ "status": "healthy", "database": "connected" }` (HTTP 200) on success, or `unhealthy` with the error message (HTTP 500) on failure.

* **FR10.2: Test Endpoint**
    * The system shall provide a public endpoint (`GET /api/test`) returning `{ "message": "Backend is working!" }` for simple connectivity verification.

### 3.3 Non-Functional Requirements

* **NFR1: Security**
    * All admin-level data must be accessible only by authenticated Admin Users.
    * Admin passwords must not be stored in plaintext. They must be hashed using `bcrypt`.
    * The system must implement role-based access control (RBAC) to differentiate 'admin' and 'manager' privileges (specifically for soft block overrides).

* **NFR2: Usability & Accessibility**
    * The public and admin frontends must be responsive and usable on mobile, tablet, and desktop devices.
    * The system must provide clear feedback to the user for all actions (e.g., success messages, validation errors) via toasts.

* **NFR3: Reliability & Data Integrity**
    * The system must prevent the creation of reservations that violate defined constraints (capacity, blocks).
    * All database operations that involve multiple steps (e.g., creating a customer and then a reservation) must use transactions that are rolled back on failure.
    * Foreign key constraints (e.g., `ON DELETE CASCADE`) must be used to ensure data integrity when parent records (like `locations`) are deleted.

* **NFR4: Performance**
    * Database indexes must be applied to all foreign keys and frequently queried columns (e.g., `reservations.date`, `reservations.time`) to ensure fast availability lookups.
    * The admin dashboard statistics (FR6.1) must be generated efficiently to avoid long load times.

* **NFR5: Testability**
    * The backend must include unit tests for pure logic functions (`utils/time_utils.py`, `utils/room_assignment.py`) and integration tests for all route blueprints (public, auth, admin CRUD, blocks, audit, dashboard, profile).
    * The frontend must include unit tests for the API service layer (`services/api.js`) and component tests for key UI components (e.g., `AdminLogin`, `Dashboard`).
    * Tests must be runnable without external dependencies (no Postgres required for the backend suite; no running backend required for the frontend suite).
