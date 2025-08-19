import os
import sqlite3
import json
import feedparser
from datetime import datetime, timedelta, timezone
from time import mktime
import time

# Config
DB_PATH = os.path.join(os.path.dirname(__file__), "data", "manuscript_db.db")
N_DAYS = 4
BATCH_SIZE = 500
ARXIV_API_URL = "http://export.arxiv.org/api/query"
PRUNE_DAYS = 730  # ~2 years

# Search categories
physics_categories = [ "astro-ph", "cond-mat.dis-nn", "cond-mat.mes-hall", "cond-mat.mtrl-sci", "cond-mat.other",
    "cond-mat.quant-gas", "cond-mat.soft", "cond-mat.stat-mech", "cond-mat.str-el", "cond-mat.supr-con",
    "gr-qc", "hep-ex", "hep-lat", "hep-ph", "hep-th", "math-ph", "nlin.AO", "nlin.CD", "nlin.CG",
    "nlin.PS", "nlin.SI", "nucl-ex", "nucl-th", "physics.acc-ph", "physics.ao-ph", "physics.app-ph",
    "physics.atm-clus", "physics.atom-ph", "physics.bio-ph", "physics.chem-ph", "physics.class-ph",
    "physics.comp-ph", "physics.data-an", "physics.ed-ph", "physics.flu-dyn", "physics.gen-ph",
    "physics.geo-ph", "physics.hist-ph", "physics.ins-det", "physics.med-ph", "physics.optics",
    "physics.plasm-ph", "physics.pop-ph", "physics.soc-ph", "physics.space-ph", "quant-ph" ]
math_categories = [ "math.AC", "math.AG", "math.AP", "math.AT", "math.CA", "math.CO", "math.CT", "math.CV",
    "math.DG", "math.DS", "math.FA", "math.GM", "math.GN", "math.GR", "math.GT", "math.HO", "math.IT", "math.KT",
    "math.LO", "math.MG", "math.MP", "math.NA", "math.NT", "math.OA", "math.OC", "math.PR", "math.QA",
    "math.RA", "math.RT", "math.SG", "math.SP", "math.ST" ]
cs_categories = [ "cs.AI", "cs.AR", "cs.CC", "cs.CE", "cs.CG", "cs.CL", "cs.CR", "cs.CV", "cs.CY", "cs.DB",
    "cs.DC", "cs.DL", "cs.DM", "cs.DS", "cs.ET", "cs.FL", "cs.GL", "cs.GR", "cs.GT", "cs.HC", "cs.IR", "cs.IT",
    "cs.LG", "cs.LO", "cs.MA", "cs.MM", "cs.MS", "cs.NA", "cs.NE", "cs.NI", "cs.OH", "cs.OS", "cs.PF", "cs.PL",
    "cs.RO", "cs.SC", "cs.SD", "cs.SE", "cs.SI", "cs.SY" ]
stat_categories = [ "stat.AP", "stat.CO", "stat.ME", "stat.ML", "stat.OT", "stat.TH" ]
qbio_categories = [ "q-bio.BM", "q-bio.CB", "q-bio.GN", "q-bio.MN", "q-bio.NC", "q-bio.OT", "q-bio.PE", "q-bio.QM", "q-bio.SC", "q-bio.TO" ]
qfin_categories = [ "q-fin.CP", "q-fin.EC", "q-fin.GN", "q-fin.MF", "q-fin.PM", "q-fin.PR", "q-fin.RM", "q-fin.ST", "q-fin.TR" ]
eess_categories = [ "eess.AS", "eess.IV", "eess.SP", "eess.SY" ]
econ_categories = [ "econ.EM", "econ.GN", "econ.TH" ]

SEARCH_QUERIES = (
    physics_categories + math_categories + cs_categories + stat_categories +
    qbio_categories + qfin_categories + eess_categories + econ_categories
)

# Ensure data directory exists
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS manuscripts (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    authors TEXT NOT NULL,
    orcids TEXT,
    keywords TEXT,
    abstract TEXT,
    link TEXT NOT NULL,
    published_timestamp TEXT NOT NULL,
    added_timestamp TEXT NOT NULL
);
"""

CREATE_FTS_SQL = """
CREATE VIRTUAL TABLE IF NOT EXISTS manuscripts_fts USING fts5(
    title, abstract, authors, keywords, content='manuscripts', content_rowid='id'
);
"""

def initialize_database():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(CREATE_TABLE_SQL)
        conn.execute(CREATE_FTS_SQL)
    print(f"Database initialized at {DB_PATH}")

def fetch_arxiv_papers_for_query(search_query, n_days, batch_size):
    cutoff = datetime.now(timezone.utc) - timedelta(days=n_days)
    all_new_papers = []
    start = 0

    while True:
        query = (
            f"{ARXIV_API_URL}?search_query={search_query}"
            f"&start={start}&max_results={batch_size}"
            f"&sortBy=submittedDate&sortOrder=descending"
        )

        print(f"\nFetching {search_query} results {start}–{start + batch_size - 1} ...")
        feed = feedparser.parse(query)

        if not feed.entries:
            print("No more entries returned from arXiv.")
            break

        batch_papers = []
        all_older = True

        for entry in feed.entries:
            published_dt = datetime.fromtimestamp(mktime(entry.published_parsed), tz=timezone.utc)

            if published_dt >= cutoff:
                all_older = False
                arxiv_id = entry.id.split('/')[-1]
                title = entry.title.strip().replace('\n', ' ')
                abstract = entry.summary.strip().replace('\n', ' ')
                authors = [author.name for author in entry.authors]
                keywords = [tag['term'] for tag in entry.tags] if 'tags' in entry else []
                link = entry.link

                batch_papers.append({
                    "id": arxiv_id,
                    "title": title,
                    "authors": json.dumps(authors),
                    "orcids": json.dumps([]),
                    "keywords": json.dumps(keywords),
                    "abstract": abstract,
                    "link": link,
                    "published_timestamp": published_dt.isoformat(),
                    "added_timestamp": datetime.now(timezone.utc).isoformat()
                })

        if feed.entries:
            first_date = datetime.fromtimestamp(mktime(feed.entries[0].published_parsed))
            last_date = datetime.fromtimestamp(mktime(feed.entries[-1].published_parsed))
            print(f"Batch covers: {first_date.date()} → {last_date.date()}")

        all_new_papers.extend(batch_papers)
        print(f"Fetched {len(feed.entries)} → Keeping {len(batch_papers)}")

        if all_older:
            print("All entries in this batch are older than cutoff — stopping.")
            break

        start += batch_size
        time.sleep(3)

    return all_new_papers

def insert_papers_to_db(papers):
    if not papers:
        print("No new papers to insert.")
        return

    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        new_count = 0
        for paper in papers:
            try:
                cursor.execute("""
                    INSERT INTO manuscripts (
                        id, title, authors, orcids, keywords, abstract,
                        link, published_timestamp, added_timestamp
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    paper["id"], paper["title"], paper["authors"],
                    paper["orcids"], paper["keywords"], paper["abstract"],
                    paper["link"], paper["published_timestamp"], paper["added_timestamp"]
                ))

                cursor.execute("""
                    INSERT INTO manuscripts_fts (rowid, title, abstract, authors, keywords)
                    VALUES ((SELECT rowid FROM manuscripts WHERE id = ?), ?, ?, ?, ?)
                """, (
                    paper["id"], paper["title"], paper["abstract"],
                    paper["authors"], paper["keywords"]
                ))

                new_count += 1
            except sqlite3.IntegrityError:
                continue  # Duplicate
        conn.commit()
    print(f"Inserted {new_count} new manuscript(s).")

def prune_old_papers(days=PRUNE_DAYS):
    """Delete manuscripts older than `days` and purge corresponding FTS rows."""
    cutoff_iso = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()

        # Collect rowids to delete first (so we can also delete from FTS)
        cur.execute("SELECT rowid FROM manuscripts WHERE published_timestamp < ?", (cutoff_iso,))
        rowids = [r[0] for r in cur.fetchall()]
        to_delete = len(rowids)

        if to_delete == 0:
            print("Prune: nothing to remove.")
            return 0

        # Build placeholder list safely
        placeholders = ",".join(["?"] * to_delete)

        # Delete from manuscripts (content table)
        cur.execute(f"DELETE FROM manuscripts WHERE rowid IN ({placeholders})", rowids)

        # Delete matching rows from FTS index
        cur.execute(f"DELETE FROM manuscripts_fts WHERE rowid IN ({placeholders})", rowids)

        conn.commit()

    print(f"Pruned {to_delete} manuscript(s) older than {days} days.")
    return to_delete

if __name__ == "__main__":
    print('')
    print(datetime.now(timezone.utc).isoformat())
    initialize_database()
    total_inserted = 0
    for query in SEARCH_QUERIES:
        new_papers = fetch_arxiv_papers_for_query(query, N_DAYS, BATCH_SIZE)
        insert_papers_to_db(new_papers)
        total_inserted += len(new_papers)
    print(f"\n✅ Done. Total new manuscripts inserted: {total_inserted}")

    # Prune anything older than ~2 years
    pruned = prune_old_papers(PRUNE_DAYS)
    print(f"🧹 Prune complete. Removed: {pruned}")
