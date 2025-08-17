import sqlite3

conn = sqlite3.connect("data/users.db")
cursor = conn.cursor()

# Add the 'lang' column if it doesn't already exist
try:
    cursor.execute("ALTER TABLE users ADD COLUMN lang TEXT DEFAULT 'en';")
    print("✅ 'lang' column added to users table.")
except sqlite3.OperationalError as e:
    if "duplicate column name" in str(e):
        print("⚠️ 'lang' column already exists.")
    else:
        print(f"❌ Error: {e}")

conn.commit()
conn.close()
