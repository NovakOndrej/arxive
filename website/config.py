import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
USER_DB_PATH = os.path.join(DATA_DIR, "users.db")
USERS_ROOT = os.path.join(DATA_DIR, "users")
MAIN_DB_PATH = os.path.join(DATA_DIR, "manuscript_db.db")
