import sqlite3
"""
One time use script to add sumarry table to the manuscript database
"""
DB_PATH = "data/manuscript_db.db"

def check_and_add_summary_column():
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()

        # Get column names from manuscripts table
        cursor.execute("PRAGMA table_info(manuscripts)")
        columns = [row[1] for row in cursor.fetchall()]

        if "summary" in columns:
            print("Table already has column 'summary'.")
            print("Columns:", columns)
        else:
            print("Column 'summary' not found. Adding it...")
            cursor.execute("ALTER TABLE manuscripts ADD COLUMN summary TEXT DEFAULT ''")
            conn.commit()
            # Fetch updated column list
            cursor.execute("PRAGMA table_info(manuscripts)")
            new_columns = [row[1] for row in cursor.fetchall()]
            print("Column added successfully.")
            print("Columns:", new_columns)

if __name__ == "__main__":
    check_and_add_summary_column()
