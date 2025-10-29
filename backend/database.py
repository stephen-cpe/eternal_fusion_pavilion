import os
import psycopg2
from psycopg2 import pool
from config import Config
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

# Keep the connection pool for direct psycopg2 access if needed (e.g., in utils)
try:
    connection_pool = psycopg2.pool.ThreadedConnectionPool(
        5,  # min connections
        20,  # max connections
        host=Config.DB_HOST,
        port=Config.DB_PORT,
        database=Config.DB_NAME,
        user=Config.DB_USER,
        password=Config.DB_PASSWORD
    )
except Exception as e:
    print(f"Error creating psycopg2 connection pool: {e}")
    # Allow the app to continue, SQLAlchemy might still work
    connection_pool = None

def get_connection():
    """Gets a connection from the psycopg2 pool."""
    if connection_pool:
        return connection_pool.getconn()
    else:
        # Fallback if pool failed (not ideal for production)
        try:
             return psycopg2.connect(
                host=Config.DB_HOST,
                port=Config.DB_PORT,
                database=Config.DB_NAME,
                user=Config.DB_USER,
                password=Config.DB_PASSWORD
            )
        except Exception as e:
            print(f"Failed to create fallback psycopg2 connection: {e}")
            raise # Re-raise the exception if connection fails

def release_connection(connection):
    """Releases a connection back to the psycopg2 pool."""
    if connection_pool:
        connection_pool.putconn(connection)
    else:
        # Close connection if pool doesn't exist
        if connection:
            connection.close()

def init_db(app):
    """Initializes SQLAlchemy with the Flask app."""
    db.init_app(app)

