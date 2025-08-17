import os
import json
import sqlite3
from datetime import datetime, timezone
from glob import glob

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
MAIN_DB_PATH = os.path.join(SCRIPT_DIR, "data", "manuscript_db.db")
USERS_ROOT = os.path.join(SCRIPT_DIR, "data", "users")

def build_fts_query_from_filter(filter_data):
    groups = filter_data.get("keyword_groups", [])
    if not groups:
        return None
    return " AND ".join(["(" + " OR ".join(group) + ")" for group in groups])

def ensure_user_db_schema(user_db_path):
    with sqlite3.connect(user_db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS manuscripts (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                authors TEXT NOT NULL,
                orcids TEXT,
                keywords TEXT,
                abstract TEXT,
                link TEXT NOT NULL,
                published_timestamp TEXT NOT NULL,
                added_timestamp TEXT NOT NULL,
                label TEXT NOT NULL CHECK(label IN ('new', 'old')),
                source_filter TEXT
            );
        """)
        conn.commit()

user_dirs = sorted(glob(os.path.join(USERS_ROOT, "user_*")))
results = []

with sqlite3.connect(MAIN_DB_PATH) as main_conn:
    main_conn.row_factory = sqlite3.Row
    main_cursor = main_conn.cursor()

    for user_dir in user_dirs:
        filter_files = glob(os.path.join(user_dir, "filter_*.json"))
        user_db_path = os.path.join(user_dir, "matches.db")
        ensure_user_db_schema(user_db_path)

        for filter_file in filter_files:
            print(f"🔍 Working on filter: {filter_file}")
            with open(filter_file, "r", encoding="utf-8") as f:
                filter_data = json.load(f)

            fts_query = build_fts_query_from_filter(filter_data)
            if not fts_query:
                print("⚠️  Skipping: No keywords defined.")
                continue

            last_scan = filter_data.get("last_scan", "1970-01-01T00:00:00")
            try:
                last_scan_dt = datetime.fromisoformat(last_scan)
                if last_scan_dt.tzinfo is None:
                    last_scan_dt = last_scan_dt.replace(tzinfo=timezone.utc)
            except ValueError:
                print("⚠️  Invalid last_scan timestamp, using fallback.")
                last_scan_dt = datetime(1970, 1, 1, tzinfo=timezone.utc)

            # FTS query
            main_cursor.execute("""
                SELECT title FROM manuscripts_fts
                WHERE manuscripts_fts MATCH ?
            """, (fts_query,))
            fts_titles = [row["title"] for row in main_cursor.fetchall()]
            print(f"📄 Found {len(fts_titles)} total matches from FTS.")

            if not fts_titles:
                # Still update timestamp to avoid infinite old scans
                filter_data["last_scan"] = datetime.now(timezone.utc).isoformat()
                with open(filter_file, "w", encoding="utf-8") as f:
                    json.dump(filter_data, f, indent=2)
                print("⏱️  No matches found — updated timestamp.")
                continue

            # Fetch all matching rows from manuscripts
            placeholder = ",".join("?" for _ in fts_titles)
            main_cursor.execute(f"""
                SELECT * FROM manuscripts
                WHERE title IN ({placeholder})
            """, fts_titles)
            all_matches = main_cursor.fetchall()

            # Filter by added_timestamp
            new_matches = []
            for row in all_matches:
                added_dt = datetime.fromisoformat(row["added_timestamp"])
                if added_dt.tzinfo is None:
                    added_dt = added_dt.replace(tzinfo=timezone.utc)
                if added_dt > last_scan_dt:
                    new_matches.append(row)

            print(f"🆕 {len(new_matches)} new matches found since last scan.")

            added_count = 0
            if new_matches:
                with sqlite3.connect(user_db_path) as user_conn:
                    user_conn.row_factory = sqlite3.Row
                    user_cursor = user_conn.cursor()
                    for match in new_matches:
                        match_dict = dict(match)
                        manuscript_id = match_dict["id"]
                        added_timestamp = match_dict["added_timestamp"]

                        user_cursor.execute("SELECT label FROM manuscripts WHERE id = ?", (manuscript_id,))
                        existing = user_cursor.fetchone()
                        label = existing["label"] if existing else "new"
                        
                        filter_name = os.path.basename(filter_file).replace("filter_", "").replace(".json", "")

                        user_cursor.execute("""
                            INSERT OR REPLACE INTO manuscripts (
                                id, title, authors, orcids, keywords,
                                abstract, link, published_timestamp,
                                added_timestamp, label, source_filter
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            manuscript_id,
                            match_dict["title"],
                            match_dict["authors"],
                            match_dict["orcids"],
                            match_dict["keywords"],
                            match_dict["abstract"],
                            match_dict["link"],
                            match_dict["published_timestamp"],
                            added_timestamp,
                            label,
                            filter_name
                        ))
                        added_count += 1
                    user_conn.commit()
            print(f"✅ Inserted {added_count} entries to {os.path.basename(user_db_path)}.")

            # Update filter's last_scan
            filter_data["last_scan"] = datetime.now(timezone.utc).isoformat()
            with open(filter_file, "w", encoding="utf-8") as f:
                json.dump(filter_data, f, indent=2)
            print("⏱️  Timestamp updated.\n")

results.append("✅ Filters processed and user match databases updated.")
print("\n".join(results))
