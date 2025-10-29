# create_admin.py
import os
import psycopg2
import bcrypt
from config import Config

def create_admin_user():
    # Connect to the database
    conn = None
    try:
        conn = psycopg2.connect(
            host=Config.DB_HOST,
            port=Config.DB_PORT,
            database=Config.DB_NAME,
            user=Config.DB_USER,
            password=Config.DB_PASSWORD
        )
        cursor = conn.cursor()

        # Hash the password 'strongpassword'
        password = "strongpassword".encode('utf-8')
        salt = bcrypt.gensalt()
        hashed_password = bcrypt.hashpw(password, salt).decode('utf-8')

        # Check if admin user already exists
        cursor.execute("SELECT id FROM admins WHERE username = %s", ('admin',))
        admin = cursor.fetchone()

        if admin:
            # Update existing admin
            cursor.execute("""
                UPDATE admins 
                SET password_hash = %s, full_name = %s, role = %s
                WHERE username = %s
            """, (hashed_password, 'Eternal Fusion Pavilion Administrator', 'admin', 'admin'))
            print("Admin user updated successfully.")
        else:
            # Create new admin
            cursor.execute("""
                INSERT INTO admins (username, password_hash, full_name, role)
                VALUES (%s, %s, %s, %s)
            """, ('admin', hashed_password, 'Eternal Fusion Pavilion Administrator', 'admin'))
            print("Admin user created successfully.")

        conn.commit()
    except Exception as e:
        print(f"Error: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    create_admin_user()