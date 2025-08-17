import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "manuscript_db.db")

def rebuild_fts():
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()

        print("Dropping corrupted FTS table...")
        cursor.execute("DROP TABLE IF EXISTS manuscripts_fts")

        print("Recreating FTS table...")
        cursor.execute("""
            CREATE VIRTUAL TABLE manuscripts_fts USING fts5(
                title, abstract, authors, keywords
            );
        """)

        print("Re-inserting data into FTS table...")
        cursor.execute("SELECT title, abstract, authors, keywords FROM manuscripts")
        rows = cursor.fetchall()
        cursor.executemany("""
            INSERT INTO manuscripts_fts (title, abstract, authors, keywords)
            VALUES (?, ?, ?, ?)
        """, rows)

        conn.commit()
        print(f"✅ Rebuilt FTS index with {len(rows)} rows.")

if __name__ == "__main__":
    rebuild_fts()
