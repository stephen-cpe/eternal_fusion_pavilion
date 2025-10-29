import os
from dotenv import load_dotenv

load_dotenv() # Load environment variables from .env file

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'generate_a_very_secret_key')
    SESSION_TYPE = 'filesystem'
    SESSION_FILE_DIR = './.flask_session/' # Ensure this directory exists
    API_PREFIX = '/api'

    # Database Configuration
    DB_HOST = os.environ.get('DB_HOST', 'localhost')
    DB_PORT = os.environ.get('DB_PORT', '5432')
    DB_NAME = os.environ.get('DB_NAME', 'eternal_fusion_pavilion_database')
    DB_USER = os.environ.get('DB_USER', 'efp_user')
    DB_PASSWORD = os.environ.get('DB_PASSWORD', 'strongpassword')

    # --- NEW: SQLAlchemy Configuration ---
    SQLALCHEMY_DATABASE_URI = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False # Recommended setting
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_size': 10,
        'max_overflow': 20,
        'pool_recycle': 3600, # Recycle connections every hour
    }
    # ------------------------------------

# Make sure SESSION_FILE_DIR exists
if not os.path.exists(Config.SESSION_FILE_DIR):
    os.makedirs(Config.SESSION_FILE_DIR)
