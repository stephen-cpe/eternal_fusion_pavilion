from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS
from flask_session import Session
from config import Config
from database import db, init_db, get_connection, release_connection
import models

from routes import (
    reservations,
    newsletter,
    admin_auth,
    admin_profile,
    admin_reservations,
    admin_blocks,
    admin_customers,
    admin_other
)

import os
import socket

def create_app():
    app = Flask(__name__, static_folder='../frontend/build', static_url_path='/')
    app.config.from_object(Config)

    init_db(app) # Initialize SQLAlchemy
    Session(app) # Initialize Flask-Session

    # Get your local IP for development
    hostname = socket.gethostname()
    local_ip = socket.gethostbyname(hostname)

    origins = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        f"http://{local_ip}:3000",
    ]
    print(f"Allowing origins: {origins}") # Helpful for debugging

    # Enable CORS
    CORS(app, supports_credentials=True, resources={
        r"/api/*": {
            "origins": origins,
            "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            "allow_headers": ["Content-Type", "Authorization"],
        }
    })

    # Register blueprints using API_PREFIX
    app.register_blueprint(reservations.bp, url_prefix=f"{Config.API_PREFIX}/reservations")
    app.register_blueprint(newsletter.bp, url_prefix=f"{Config.API_PREFIX}/newsletter")

    admin_prefix = f"{Config.API_PREFIX}/admin"
    app.register_blueprint(admin_auth.bp, url_prefix=admin_prefix)
    app.register_blueprint(admin_profile.bp, url_prefix=admin_prefix)
    app.register_blueprint(admin_reservations.bp, url_prefix=admin_prefix)
    app.register_blueprint(admin_blocks.bp, url_prefix=admin_prefix)
    app.register_blueprint(admin_customers.bp, url_prefix=admin_prefix)
    app.register_blueprint(admin_other.bp, url_prefix=admin_prefix)

    @app.route('/api/health', methods=['GET'])
    def health_check():
        db_status = 'disconnected'
        db_error = None
        # Test SQLAlchemy connection
        try:
            # A simple query to check the connection
            db.session.execute(db.text('SELECT 1'))
            db_status = 'connected'
        except Exception as e:
            db_error = str(e)
            app.logger.error(f"Database health check failed: {e}")

        # You might optionally keep the psycopg2 check if needed elsewhere
        # psycopg2_status = 'disconnected'
        # conn = None
        # try:
        #     conn = get_connection()
        #     with conn.cursor() as cursor:
        #         cursor.execute('SELECT 1')
        #         cursor.fetchone()
        #     psycopg2_status = 'connected'
        # except Exception as e:
        #     psycopg2_status = f'disconnected: {str(e)}'
        # finally:
        #     if conn:
        #         release_connection(conn)

        if db_status == 'connected':
            return jsonify({'status': 'healthy', 'database': db_status})
        else:
            return jsonify({'status': 'unhealthy', 'database': db_status, 'error': db_error}), 500


    @app.route('/api/test', methods=['GET'])
    def test_endpoint():
        return jsonify({'message': 'Backend is working!'})

    # Serve React App
    @app.route('/', defaults={'path': ''})
    @app.route('/<path:path>')
    def serve(path):
        if path != "" and os.path.exists(os.path.join(app.static_folder, path)):
            return send_from_directory(app.static_folder, path)
        else:
            # Serve index.html for SPA routing
            return send_from_directory(app.static_folder, 'index.html')

    return app

if __name__ == '__main__':
    app = create_app()
    # Use Flask's development server, debug=True enables auto-reloading
    app.run(debug=True, port=5000, host='0.0.0.0')
