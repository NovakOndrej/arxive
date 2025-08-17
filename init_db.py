import os
import sqlite3

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "manuscript_db.db")

def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()

        # Create main manuscripts table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS manuscripts (
                id TEXT PRIMARY KEY,
                title TEXT,
                authors TEXT,
                orcids TEXT,
                keywords TEXT,
                abstract TEXT,
                link TEXT,
                published_timestamp TEXT,
                added_timestamp TEXT
            )
        """)

        # Create FTS5 table for full-text search
        cursor.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS fts_manuscripts
            USING fts5(title, abstract, keywords, authors, content='manuscripts', content_rowid='id');
        """)

        conn.commit()

if __name__ == "__main__":
    init_db()
    print("✅ Database initialized.")
