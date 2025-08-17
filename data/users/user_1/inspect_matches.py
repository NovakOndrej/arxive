import os
import sqlite3
from pprint import pprint

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(SCRIPT_DIR, "matches.db")

print(f"📂 Inspecting: {DB_PATH}")

if not os.path.exists(DB_PATH):
    print("❌ matches.db not found.")
    exit(1)

try:
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM manuscripts")
        total = cursor.fetchone()[0]
        print(f"📄 Total entries: {total}")

        cursor.execute("SELECT * FROM manuscripts LIMIT 2")
        entries = cursor.fetchall()

        for i, entry in enumerate(entries, 1):
            print(f"\n--- Entry {i} ---")
            pprint(dict(entry))

except sqlite3.Error as e:
    print(f"❌ SQLite error: {e}")
