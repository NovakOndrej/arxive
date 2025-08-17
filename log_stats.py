import os
import sqlite3
from datetime import datetime
from glob import glob

# --- Config ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
USERS_ROOT = os.path.join(SCRIPT_DIR, "data", "users")
STATS_DB_PATH = os.path.abspath(os.path.join(SCRIPT_DIR, "..", "stats", "services", "arxiv_stats.db"))

# --- Ensure stats directory exists ---
os.makedirs(os.path.dirname(STATS_DB_PATH), exist_ok=True)

# --- Initialize database if needed ---
def init_stats_db():
    with sqlite3.connect(STATS_DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS usage_stats (
                timestamp TEXT NOT NULL,
                num_users INTEGER,
                num_filters INTEGER,
                num_recommendations INTEGER
            )
        """)
        conn.commit()

# --- Collect statistics ---
def collect_stats():
    num_users = 0
    num_filters = 0
    num_recommendations = 0

    user_dirs = sorted(glob(os.path.join(USERS_ROOT, "user_*")))
    num_users = len(user_dirs)

    for user_dir in user_dirs:
        # Count filter files
        filter_files = glob(os.path.join(user_dir, "filter_*.json"))
        num_filters += len(filter_files)

        # Count entries in matches.db
        user_db_path = os.path.join(user_dir, "matches.db")
        if os.path.exists(user_db_path):
            try:
                with sqlite3.connect(user_db_path) as user_conn:
                    cursor = user_conn.cursor()
                    cursor.execute("SELECT COUNT(*) FROM manuscripts")
                    count = cursor.fetchone()[0]
                    num_recommendations += count
            except Exception as e:
                print(f"⚠️ Error reading {user_db_path}: {e}")

    return num_users, num_filters, num_recommendations

# --- Save stats to database ---
def save_stats(timestamp, num_users, num_filters, num_recommendations):
    with sqlite3.connect(STATS_DB_PATH) as conn:
        conn.execute("""
            INSERT INTO usage_stats (timestamp, num_users, num_filters, num_recommendations)
            VALUES (?, ?, ?, ?)
        """, (timestamp, num_users, num_filters, num_recommendations))
        conn.commit()

# --- Run ---
def main():
    print("📊 Logging usage statistics...")
    init_stats_db()
    num_users, num_filters, num_recommendations = collect_stats()
    timestamp = datetime.utcnow().isoformat()
    save_stats(timestamp, num_users, num_filters, num_recommendations)
    print(f"✅ Stats recorded at {timestamp}: Users={num_users}, Filters={num_filters}, Recommendations={num_recommendations}")

if __name__ == "__main__":
    main()
