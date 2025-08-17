import sqlite3
import os
import json
from datetime import datetime

DB_FILENAME = "manuscript_db.db"
DB_PATH = os.path.join(os.path.dirname(__file__), DB_FILENAME)

def inspect_database(db_path, print_samples=True, inspect_fts=True):
    if not os.path.exists(db_path):
        print(f"Database not found at {db_path}")
        return

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # --- Main table: manuscripts ---
        cursor.execute("SELECT COUNT(*) FROM manuscripts")
        total_main = cursor.fetchone()[0]
        print(f"Total entries in manuscripts table: {total_main}")

        cursor.execute("SELECT MIN(published_timestamp), MAX(published_timestamp) FROM manuscripts")
        oldest, newest = cursor.fetchone()
        if oldest and newest:
            oldest_ts = datetime.fromisoformat(oldest)
            newest_ts = datetime.fromisoformat(newest)
            print(f"  Oldest submission: {oldest_ts.strftime('%Y-%m-%d %H:%M')}")
            print(f"  Latest submission: {newest_ts.strftime('%Y-%m-%d %H:%M')}")
        else:
            print("  No publication timestamps found.")

        if print_samples:
            cursor.execute("""
                SELECT id, title, authors, keywords, abstract
                FROM manuscripts
                ORDER BY added_timestamp DESC
                LIMIT 5
            """)
            print("\nLast 5 entries in manuscripts:\n")
            for row in cursor.fetchall():
                print(f"ID: {row['id']}")
                print(f"Title: {row['title']}")
                print(f"Authors: {json.loads(row['authors'])}")
                print(f"Keywords: {json.loads(row['keywords'])}")
                print(f"Abstract: {row['abstract'][:200]}...")
                print("-" * 60)

        # --- FTS5 table: manuscripts_fts ---
        if inspect_fts:
            try:
                cursor.execute("SELECT COUNT(*) FROM manuscripts_fts")
                total_fts = cursor.fetchone()[0]
                print(f"\nTotal entries in manuscripts_fts table: {total_fts}")

                if print_samples:
                    cursor.execute("""
                        SELECT rowid, title, abstract, authors, keywords
                        FROM manuscripts_fts
                        LIMIT 5
                    """)
                    print("\nFirst 5 entries in manuscripts_fts:\n")
                    for row in cursor.fetchall():
                        print(f"rowid: {row['rowid']}")
                        print(f"Title: {row['title']}")
                        print(f"Authors: {json.loads(row['authors'])}")
                        print(f"Keywords: {json.loads(row['keywords'])}")
                        print(f"Abstract: {row['abstract'][:200]}...")
                        print("-" * 60)

            except sqlite3.OperationalError as e:
                print("\n⚠️ Could not query FTS5 table — does it exist?")
                print("Error:", e)

if __name__ == "__main__":
    inspect_database(DB_PATH, print_samples=True, inspect_fts=True)
