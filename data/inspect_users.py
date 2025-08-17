import sqlite3
import os

# Path to the database (same directory as this script)
DB_PATH = os.path.join(os.path.dirname(__file__), "users.db")

def inspect_users():
    if not os.path.exists(DB_PATH):
        print(f"❌ Database not found at: {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT * FROM users")
        rows = cursor.fetchall()

        if not rows:
            print("ℹ️ No users found.")
            return

        print(f"✅ Found {len(rows)} users:\n")
        for row in rows:
            user_info = ", ".join([f"{key}={row[key]}" for key in row.keys()])
            print(f"– {user_info}")

    except sqlite3.Error as e:
        print(f"❌ SQLite error: {e}")

    finally:
        conn.close()

if __name__ == "__main__":
    inspect_users()
